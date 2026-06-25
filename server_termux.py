"""
CinePix Server - Termux Edition (No FastAPI, No Pydantic)
Uses Python built-in http.server — works on Android Termux
"""
import asyncio
import concurrent.futures
import json
import time
import threading
import re
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

from cache import init_db, cache_get, cache_set, cache_stats, cache_clear
from tmdb import search_tmdb, get_tv_season
from client import close as close_clients
from providers.cinefreak import cinefreak
from providers.mlsbd import mlsbd
from providers.hdhub4u import hdhub4u
from providers.southfreak import southfreak
from providers.bollyflix import bollyflix
from providers.flixsearch import flixsearch
from providers.domain_discovery import discover_deep
from providers.domain_health import check_all_domains, get_all_status
import providers.auto_resolver as auto_resolver

executor = concurrent.futures.ThreadPoolExecutor(max_workers=50)

_mem_cache = {}
_mem_cache_ttl = 600
_mem_lock = threading.Lock()
_mem_max = 500

_inflight = {}
_inflight_lock = threading.Lock()

_provider_stats = {}
_provider_lock = threading.Lock()

def mem_cache_get(key):
    with _mem_lock:
        if key in _mem_cache:
            data, ts = _mem_cache[key]
            if time.time() - ts < _mem_cache_ttl:
                return data
            del _mem_cache[key]
    return None

def mem_cache_set(key, data):
    with _mem_lock:
        if len(_mem_cache) >= _mem_max:
            oldest = min(_mem_cache, key=lambda k: _mem_cache[k][1])
            del _mem_cache[oldest]
        _mem_cache[key] = (data, time.time())

def get_inflight(key):
    with _inflight_lock:
        return _inflight.get(key)

def set_inflight(key, event):
    with _inflight_lock:
        _inflight[key] = event

def remove_inflight(key):
    with _inflight_lock:
        _inflight.pop(key, None)

def record_provider(name, success, duration):
    with _provider_lock:
        if name not in _provider_stats:
            _provider_stats[name] = {"success": 0, "fail": 0, "total_time": 0, "calls": 0}
        s = _provider_stats[name]
        s["calls"] += 1
        s["total_time"] += duration
        if success:
            s["success"] += 1
        else:
            s["fail"] += 1

def get_provider_health():
    with _provider_lock:
        return dict(_provider_stats)

def check_rate_limit(ip):
    return True

def _enrich_source(s):
    url = s.get("url", "")
    if not s.get("format"):
        if ".m3u8" in url:
            s["format"] = "hls"
        elif ".mpd" in url:
            s["format"] = "dash"
        elif ".mkv" in url:
            s["format"] = "mkv"
        else:
            s["format"] = "mp4"

_startup_time = time.time()

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CinePix</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#06070b;color:#e8ecf1;font-family:system-ui,sans-serif;min-height:100vh}
.hero{padding:48px 24px;text-align:center}
.hero h1{font-size:36px;font-weight:900;letter-spacing:4px}
.hero h1 span{background:linear-gradient(135deg,#00ff88,#22d3ee);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero p{color:#7b8394;font-size:12px;letter-spacing:2px;text-transform:uppercase;margin-top:8px}
.search-box{display:flex;gap:10px;max-width:600px;margin:24px auto;padding:0 20px}
.search-box input{flex:1;background:#0d0f14;color:#e8ecf1;border:1px solid #262a3a;padding:14px 20px;border-radius:12px;font-size:15px;outline:none}
.search-box button{background:linear-gradient(135deg,#00ff88,#22d3ee);color:#000;border:none;padding:14px 24px;border-radius:12px;font-weight:700;cursor:pointer}
.results{max-width:800px;margin:0 auto;padding:20px}
.card{background:#0d0f14;border:1px solid #1e2130;border-radius:12px;padding:14px;margin:8px 0;cursor:pointer;display:flex;gap:12px;align-items:center}
.card:hover{border-color:#00ff88}
.card img{width:50px;height:75px;border-radius:8px;object-fit:cover}
.card-info h3{font-size:14px;font-weight:700}
.card-info p{font-size:12px;color:#7b8394}
.sources{margin-top:16px}
.src{background:#13151c;border-radius:10px;padding:12px;margin:6px 0;border:1px solid transparent}
.src:hover{border-color:#1e2130}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:#00ff8820;color:#00ff88;margin-right:4px}
.btn{padding:6px 12px;border-radius:6px;border:none;font-size:11px;font-weight:700;cursor:pointer;margin:2px}
.btn-play{background:#00b894;color:#fff}
.btn-copy{background:#1a1d26;color:#7b8394;border:1px solid #262a3a}
</style>
</head>
<body>
<div class="hero">
<h1>CINE<span>PIX</span></h1>
<p>Multi-Source Streaming Engine</p>
</div>
<div class="search-box">
<input id="q" placeholder="Search movies or TV shows..." onkeypress="if(event.key==='Enter')doSearch()">
<button onclick="doSearch()">Search</button>
</div>
<div class="results" id="r"></div>
<script>
function doSearch(){
var q=document.getElementById('q').value.trim();
if(!q)return;
document.getElementById('r').innerHTML='<p style="color:#7b8394;text-align:center">Searching...</p>';
fetch('/v1/search?q='+encodeURIComponent(q)).then(r=>r.json()).then(d=>{
var h='';
(d.results||[]).forEach(function(i){
h+='<div class="card" onclick="loadSrc('+i.id+',\\''+i.type+'\\',\\''+i.title.replace(/'/g,"\\\\'")+'\\')">';
if(i.poster)h+='<img src="'+i.poster+'" onerror="this.style.display=\\'none\\'">';
h+='<div class="card-info"><h3>'+i.title+'</h3><p>'+(i.year||'')+' | '+i.type.toUpperCase()+'</p></div></div>';
});
document.getElementById('r').innerHTML=h||'<p style="color:#7b8394;text-align:center">No results</p>';
});
}
function loadSrc(id,type,title){
document.getElementById('r').innerHTML='<p style="color:#7b8394;text-align:center">Loading sources for '+title+'...</p>';
var url='/v1/movies/'+id+'/sources/stream?type='+type+'&title='+encodeURIComponent(title);
var es=new EventSource(url);
var html='<p style="margin-bottom:8px"><b>'+title+'</b> <a href="#" onclick="es.close();doSearch();return false" style="color:#22d3ee;font-size:12px">← Back</a></p><div class="sources" id="src"></div>';
document.getElementById('r').innerHTML=html;
var n=0;
es.onmessage=function(e){
var m=JSON.parse(e.data);
if(m.type==='provider_done'){
(m.sources||[]).forEach(function(s){
n++;
var el=document.createElement('div');
el.className='src';
el.innerHTML='<span class="badge">'+(s.quality||'HD')+'</span><span class="badge">'+(s.provider||'')+'</span><span class="badge">'+(s.format||'')+'</span>'
+'<br><small style="color:#454b5e">'+s.url.substring(0,80)+'...</small><br>'
+'<button class="btn btn-play" onclick="window.open(\\''+s.url.replace(/'/g,"\\\\'")+'\\')">&#9654; Play</button>'
+'<button class="btn btn-copy" onclick="navigator.clipboard.writeText(\\''+s.url.replace(/'/g,"\\\\'")+'\\');this.textContent=\\'Copied!\\'">Copy</button>';
document.getElementById('src').appendChild(el);
});
}
if(m.type==='done'){
es.close();
if(n===0)document.getElementById('src').innerHTML='<p style="color:#7b8394">No sources found</p>';
}
};
es.onerror=function(){es.close();};
}
</script>
</body>
</html>"""


class CinePixHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_sse_headers(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/":
            body = HTML_PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/health":
            self._send_json({"status": "ok", "service": "CinePix Termux", "version": "3.1"})
            return

        if path == "/v1/search":
            q = params.get("q", [""])[0]
            if not q:
                self._send_json({"results": [], "count": 0})
                return
            loop = asyncio.new_event_loop()
            try:
                results = loop.run_until_complete(search_tmdb(q))
            finally:
                loop.close()
            self._send_json({"results": results, "count": len(results)})
            return

        if path.startswith("/v1/tv/") and "/season/" in path:
            parts = path.split("/")
            tv_id = parts[3]
            season = parts[5] if len(parts) > 5 else "1"
            loop = asyncio.new_event_loop()
            try:
                data = loop.run_until_complete(get_tv_season(tv_id, int(season)))
            finally:
                loop.close()
            self._send_json(data)
            return

        if path.startswith("/v1/movies/") and path.endswith("/sources/stream"):
            parts = path.split("/")
            tmdb_id = parts[3]
            type_val = params.get("type", ["movie"])[0]
            title = params.get("title", [""])[0]
            season = int(params.get("season", ["0"])[0])
            episode = int(params.get("episode", ["0"])[0])

            self._send_sse_headers()

            providers_list = [
                ("CineFreak", lambda: cinefreak(tmdb_id, type_val, title, season, episode)),
                ("HDHub4U", lambda: hdhub4u(title, tmdb_id)),
                ("MLSBD", lambda: mlsbd(title, tmdb_id)),
                ("SouthFreak", lambda: southfreak(title, tmdb_id)),
                ("BollyFlix", lambda: bollyflix(title, tmdb_id)),
                ("FlixSearch", lambda: flixsearch(title, tmdb_id)),
            ]

            seen_urls = set()
            count = 0

            for name, func in providers_list:
                start_msg = json.dumps({"type": "provider_start", "name": name})
                self.wfile.write(f"data: {start_msg}\n\n".encode())
                self.wfile.flush()

                t0 = time.time()
                try:
                    result = func()
                except Exception:
                    result = []
                duration = time.time() - t0
                record_provider(name, bool(result), duration)

                new_sources = []
                for s in (result or []):
                    url = s.get("url", "").split("?")[0].rstrip("/")
                    if url not in seen_urls:
                        seen_urls.add(url)
                        _enrich_source(s)
                        new_sources.append(s)
                        count += 1

                done_msg = json.dumps({
                    "type": "provider_done", "name": name, "sources": new_sources,
                    "count": len(new_sources), "done": providers_list.index((name, func)) + 1,
                    "total": len(providers_list)
                })
                self.wfile.write(f"data: {done_msg}\n\n".encode())
                self.wfile.flush()

            done_msg = json.dumps({"type": "done", "total_sources": count})
            self.wfile.write(f"data: {done_msg}\n\n".encode())
            self.wfile.flush()
            return

        if path == "/api/admin/domains":
            self._send_json({"domains": []})
            return

        self._send_json({"error": "Not found"}, 404)


def run_server():
    init_db()
    print("=" * 50)
    print("  CinePix Server v3.1 Termux Edition")
    print("  No FastAPI, No Pydantic - Pure Python")
    print("  Port: 8000")
    print("  Providers: 6")
    print("=" * 50)

    server = HTTPServer(("0.0.0.0", 8000), CinePixHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        close_clients()
        executor.shutdown(wait=False)


if __name__ == "__main__":
    run_server()
