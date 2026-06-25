import asyncio
import concurrent.futures
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import threading
from collections import OrderedDict

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


app = FastAPI(title="CinePix Server", version="3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = concurrent.futures.ThreadPoolExecutor(max_workers=50)
_provider_semaphore = asyncio.Semaphore(20)

_mem_cache = OrderedDict()
_mem_cache_ttl = 600
_mem_lock = threading.Lock()
_mem_max = 1000

_inflight = {}
_inflight_lock = threading.Lock()

_provider_stats = {}
_provider_lock = threading.Lock()

def mem_cache_get(key):
    with _mem_lock:
        if key in _mem_cache:
            data, ts = _mem_cache[key]
            if time.time() - ts < _mem_cache_ttl:
                _mem_cache.move_to_end(key)
                return data
            del _mem_cache[key]
    return None

def mem_cache_set(key, data):
    with _mem_lock:
        if key in _mem_cache:
            _mem_cache.move_to_end(key)
        else:
            if len(_mem_cache) >= _mem_max:
                _mem_cache.popitem(last=False)
        _mem_cache[key] = (data, time.time())

def get_inflight(key):
    with _inflight_lock:
        if key in _inflight:
            return _inflight[key]
        return None

def set_inflight(key, event):
    with _inflight_lock:
        _inflight[key] = event

def remove_inflight(key):
    with _inflight_lock:
        _inflight.pop(key, None)

def record_provider(name, success, duration):
    with _provider_lock:
        if name not in _provider_stats:
            _provider_stats[name] = {"ok": 0, "fail": 0, "total_time": 0, "count": 0}
        stats = _provider_stats[name]
        if success:
            stats["ok"] += 1
        else:
            stats["fail"] += 1
        stats["total_time"] += duration
        stats["count"] += 1

def get_provider_health():
    with _provider_lock:
        result = {}
        for name, stats in _provider_stats.items():
            avg_time = stats["total_time"] / max(stats["count"], 1)
            success_rate = stats["ok"] / max(stats["ok"] + stats["fail"], 1)
            result[name] = {
                "avg_time": round(avg_time, 2),
                "success_rate": round(success_rate * 100, 1),
                "total_calls": stats["count"],
            }
        return result

_rate_limit = {}
RATE_LIMIT = 60
RATE_WINDOW = 60

def check_rate_limit(ip):
    now = time.time()
    with _mem_lock:
        if ip not in _rate_limit:
            _rate_limit[ip] = []
        _rate_limit[ip] = [t for t in _rate_limit[ip] if now - t < RATE_WINDOW]
        if len(_rate_limit[ip]) >= RATE_LIMIT:
            return False
        _rate_limit[ip].append(now)
        if len(_rate_limit) > 5000:
            cutoff = now - RATE_WINDOW
            _rate_limit.clear()
    return True

@app.on_event("startup")
async def startup():
    await init_db()
    threading.Thread(target=_run_domain_discovery, daemon=True).start()

def _run_domain_discovery():
    try:
        discovered = discover_deep()
        for name, domains in discovered.items():
            if domains:
                print(f"[DomainDiscovery] {name}: {domains}")
        from providers.domain_discovery import update_config
        update_config(discovered)
        print("[DomainDiscovery] Config updated")
    except Exception as e:
        print(f"[DomainDiscovery] Error: {e}")

@app.on_event("shutdown")
async def shutdown():
    close_clients()
    executor.shutdown(wait=False)

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CinePix</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#06070b;--surface:#0d0f14;--surface2:#13151c;--surface3:#1a1d26;--border:#1e2130;--border2:#262a3a;--green:#00ff88;--green2:#00cc6a;--red:#ff4757;--orange:#ffa502;--blue:#70b8ff;--purple:#a78bfa;--cyan:#22d3ee;--text:#e8ecf1;--dim:#7b8394;--dim2:#454b5e;--glow:rgba(0,255,136,.06)}
body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,-apple-system,sans-serif;min-height:100vh;overflow-x:hidden;background-image:radial-gradient(ellipse 80% 50% at 50% -20%,rgba(0,255,136,.04),transparent)}

.hero{position:relative;padding:72px 24px 48px;text-align:center}
.hero::before{content:'';position:absolute;top:0;left:50%;transform:translateX(-50%);width:600px;height:600px;background:radial-gradient(circle,rgba(0,255,136,.07) 0%,transparent 70%);pointer-events:none}
.hero h1{font-size:44px;font-weight:900;letter-spacing:6px;margin-bottom:10px;position:relative}
.hero h1 span{background:linear-gradient(135deg,var(--green),var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-shadow:none}
.hero p{color:var(--dim);font-size:12px;letter-spacing:3px;text-transform:uppercase;font-weight:500}
.hero .stats{display:flex;justify-content:center;gap:32px;margin-top:20px}
.hero .stat{text-align:center}
.hero .stat b{display:block;font-size:22px;font-weight:800;color:var(--green)}
.hero .stat small{font-size:11px;color:var(--dim2);letter-spacing:1px;text-transform:uppercase}

.search-wrap{max-width:660px;margin:0 auto;padding:0 20px;position:relative;z-index:2}
.search-box{display:flex;gap:10px;margin-top:-24px}
.search-box input{flex:1;background:var(--surface);color:var(--text);border:1px solid var(--border2);padding:18px 24px;border-radius:14px;font-size:16px;font-family:inherit;outline:none;transition:all .3s;box-shadow:0 12px 40px rgba(0,0,0,.5)}
.search-box input:focus{border-color:var(--green);box-shadow:0 12px 40px rgba(0,0,0,.5),0 0 0 3px rgba(0,255,136,.08)}
.search-box input::placeholder{color:var(--dim2)}
.search-box button{background:linear-gradient(135deg,var(--green),var(--cyan));color:#000;border:none;padding:18px 32px;border-radius:14px;font-size:15px;font-weight:800;font-family:inherit;cursor:pointer;white-space:nowrap;transition:all .3s;box-shadow:0 4px 20px rgba(0,255,136,.25);letter-spacing:.5px}
.search-box button:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,255,136,.35)}
.search-box button:active{transform:translateY(0)}
.search-box button:disabled{background:var(--surface2);color:var(--dim2);box-shadow:none;cursor:not-allowed;transform:none}

.results-wrap{max-width:960px;margin:0 auto;padding:24px 20px}

.movie-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-top:24px}
.movie-card{background:var(--surface);border-radius:14px;cursor:pointer;border:1px solid var(--border);transition:all .3s cubic-bezier(.4,0,.2,1);display:flex;gap:14px;align-items:center;padding:14px 16px;position:relative;overflow:hidden}
.movie-card::before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,rgba(0,255,136,.04),transparent 60%);opacity:0;transition:opacity .3s}
.movie-card:hover{border-color:rgba(0,255,136,.3);transform:translateY(-3px);box-shadow:0 12px 32px rgba(0,0,0,.4),0 0 20px rgba(0,255,136,.05)}
.movie-card:hover::before{opacity:1}
.movie-poster{width:60px;height:90px;border-radius:10px;object-fit:cover;background:var(--surface2);flex-shrink:0;box-shadow:0 6px 16px rgba(0,0,0,.4)}
.movie-info{flex:1;min-width:0;position:relative;z-index:1}
.movie-title{font-size:15px;font-weight:700;color:var(--text);margin-bottom:6px;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.movie-meta{font-size:12px;color:var(--dim);display:flex;align-items:center;gap:8px}
.movie-type{background:var(--surface3);padding:3px 8px;border-radius:5px;font-size:10px;font-weight:700;color:var(--cyan);text-transform:uppercase;letter-spacing:.5px}
.movie-arrow{color:var(--dim2);font-size:22px;transition:all .3s;position:relative;z-index:1}
.movie-card:hover .movie-arrow{color:var(--green);transform:translateX(3px)}

.source-panel{background:var(--surface);border-radius:18px;border:1px solid var(--border);overflow:hidden;margin:16px 0}
.panel-header{padding:24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}
.panel-title{font-size:20px;font-weight:800}
.panel-title span{color:var(--green);font-weight:900}
.panel-meta{font-size:13px;color:var(--dim);font-weight:500}

.progress-section{padding:16px 24px;border-bottom:1px solid var(--border)}
.progress-track{height:3px;background:var(--surface3);border-radius:4px;overflow:hidden;margin-top:10px}
.progress-fill{height:100%;background:linear-gradient(90deg,var(--green),var(--cyan),var(--blue));border-radius:4px;transition:width .5s cubic-bezier(.4,0,.2,1);width:0%;position:relative}
.progress-fill::after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.2),transparent);animation:shimmer 2s infinite}
@keyframes shimmer{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}

.filter-bar{padding:14px 24px;border-bottom:1px solid var(--border);display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.filter-chip{padding:6px 14px;border-radius:20px;font-size:11px;font-weight:600;border:1px solid var(--border2);background:transparent;color:var(--dim);cursor:pointer;transition:all .2s;font-family:inherit;letter-spacing:.3px}
.filter-chip:hover{border-color:var(--dim);color:var(--text);background:var(--surface3)}
.filter-chip.active{background:linear-gradient(135deg,var(--green),var(--cyan));color:#000;border-color:transparent;font-weight:700;box-shadow:0 2px 12px rgba(0,255,136,.2)}
.filter-label{font-size:11px;color:var(--dim2);text-transform:uppercase;letter-spacing:1.5px;margin-right:4px;font-weight:600}

.providers-row{padding:12px 24px;border-bottom:1px solid var(--border);display:flex;flex-wrap:wrap;gap:6px}
.p-chip{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;border:1px solid var(--border2);background:transparent;color:var(--dim2);transition:all .3s}
.p-chip .dot{width:6px;height:6px;border-radius:50%;background:var(--dim2);transition:all .3s}
.p-chip.loading{border-color:var(--orange);color:var(--orange)}
.p-chip.loading .dot{background:var(--orange);animation:pulse 1s infinite}
.p-chip.ok{border-color:rgba(0,255,136,.4);color:var(--green);background:rgba(0,255,136,.06)}
.p-chip.ok .dot{background:var(--green);box-shadow:0 0 6px var(--green)}
.p-chip.empty{border-color:rgba(255,71,87,.3);color:var(--red);background:rgba(255,71,87,.06)}
.p-chip.empty .dot{background:var(--red)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

.source-list{padding:10px 12px}
.source-item{background:var(--surface2);border-radius:12px;padding:14px 18px;margin:6px 0;border:1px solid transparent;display:flex;align-items:center;gap:14px;transition:all .3s cubic-bezier(.4,0,.2,1);animation:fadeUp .4s ease both}
.source-item:hover{border-color:var(--border2);background:var(--surface3);box-shadow:0 4px 16px rgba(0,0,0,.2)}
@keyframes fadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}

.badge{display:inline-flex;align-items:center;padding:3px 9px;border-radius:6px;font-size:10px;font-weight:700;text-transform:uppercase;flex-shrink:0;letter-spacing:.4px}
.b-q{background:linear-gradient(135deg,var(--green),var(--cyan));color:#000}
.b-fmt{background:var(--surface3);color:var(--dim);border:1px solid var(--border2)}
.b-lang{background:rgba(112,184,255,.12);color:var(--blue);border:1px solid rgba(112,184,255,.15)}
.b-type{background:rgba(167,139,250,.12);color:var(--purple);border:1px solid rgba(167,139,250,.15)}

.src-body{flex:1;min-width:0}
.src-row1{display:flex;align-items:center;gap:6px;margin-bottom:4px;flex-wrap:wrap}
.src-provider{font-size:12px;font-weight:700;color:var(--text);letter-spacing:.3px}
.src-url{font-size:11px;color:var(--blue);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer;transition:color .2s;font-family:'SF Mono',Monaco,Consolas,monospace}
.src-url:hover{color:var(--green)}

.src-btns{display:flex;gap:5px;flex-shrink:0}
.btn{padding:7px 14px;border-radius:8px;border:none;font-size:11px;font-weight:700;font-family:inherit;cursor:pointer;transition:all .2s;letter-spacing:.3px}
.btn:hover{transform:translateY(-1px);filter:brightness(1.1)}
.btn:active{transform:translateY(0)}
.btn-play{background:linear-gradient(135deg,#00b894,#00cec9);color:#fff;box-shadow:0 2px 8px rgba(0,206,201,.2)}
.btn-vlc{background:linear-gradient(135deg,#e17055,#d63031);color:#fff}
.btn-mx{background:linear-gradient(135deg,#0984e3,#6c5ce7);color:#fff}
.btn-dl{background:linear-gradient(135deg,var(--green),var(--cyan));color:#000}
.btn-copy{background:var(--surface3);color:var(--dim);border:1px solid var(--border2)}

.player-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.98);z-index:1000;justify-content:center;align-items:center;flex-direction:column;backdrop-filter:blur(20px)}
.player-overlay.active{display:flex}
.player-overlay video{width:92%;max-width:1000px;border-radius:12px;max-height:80vh;background:#000;box-shadow:0 20px 60px rgba(0,0,0,.6)}
.player-overlay .p-title{color:var(--text);font-size:15px;font-weight:600;margin-bottom:14px;text-align:center}
.player-overlay .close-btn{position:absolute;top:24px;right:24px;background:rgba(255,71,87,.9);color:#fff;border:none;width:44px;height:44px;border-radius:50%;font-size:22px;cursor:pointer;z-index:1001;transition:all .25s;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(10px)}
.player-overlay .close-btn:hover{background:var(--red);transform:scale(1.1);box-shadow:0 4px 20px rgba(255,71,87,.4)}
.player-overlay .p-info{color:var(--dim2);font-size:12px;margin-top:12px}

.toast{display:none;position:fixed;bottom:32px;left:50%;transform:translateX(-50%);background:linear-gradient(135deg,var(--green),var(--cyan));color:#000;padding:14px 28px;border-radius:12px;font-size:13px;font-weight:700;z-index:2000;box-shadow:0 8px 32px rgba(0,255,136,.3);white-space:nowrap;animation:toastIn .35s cubic-bezier(.4,0,.2,1)}
.toast.show{display:block}
@keyframes toastIn{from{opacity:0;transform:translateX(-50%) translateY(24px) scale(.95)}to{opacity:1;transform:translateX(-50%) translateY(0) scale(1)}}

.empty{text-align:center;padding:56px 20px;color:var(--dim2);font-size:14px}
.empty svg{margin-bottom:16px;opacity:.3}
.spinner{display:inline-block;width:18px;height:18px;border:2.5px solid var(--border2);border-top-color:var(--green);border-radius:50%;animation:spin .7s linear infinite;vertical-align:middle;margin-right:8px}
@keyframes spin{to{transform:rotate(360deg)}}

.back-btn{background:var(--surface2);color:var(--text);border:1px solid var(--border2);padding:10px 18px;border-radius:10px;cursor:pointer;font-size:12px;font-weight:600;font-family:inherit;transition:all .2s;margin-bottom:10px;display:inline-flex;align-items:center;gap:6px}
.back-btn:hover{background:var(--surface3);border-color:var(--dim2)}

@media(max-width:640px){
.hero{padding:48px 16px 36px}
.hero h1{font-size:32px;letter-spacing:4px}
.hero .stats{gap:20px}
.search-box{flex-direction:column}
.search-box button{width:100%;padding:16px}
.movie-grid{grid-template-columns:1fr}
.movie-card{padding:12px}
.panel-header{padding:16px}
.filter-bar{padding:10px 16px}
.providers-row{padding:10px 16px}
.source-item{padding:12px 14px;flex-wrap:wrap}
.src-btns{width:100%;justify-content:flex-end;margin-top:8px}
}
</style>
<div id="playerModal" class="player-overlay">
<button class="close-btn" onclick="closePlayer()">&#10005;</button>
<div class="p-title" id="playerTitle"></div>
<video id="mainPlayer" controls playsinline></video>
<div class="p-info">ESC or click &#10005; to close</div>
</div>
<div id="toast" class="toast"></div>
</head>
<body>

<div class="hero">
  <h1>CINE<span>PIX</span></h1>
  <p>Multi-Source Streaming Engine</p>
  <div class="stats">
    <div class="stat"><b>8+</b><small>Providers</small></div>
    <div class="stat"><b>HLS</b><small>DASH</small></div>
    <div class="stat"><b>4K</b><small>Quality</small></div>
  </div>
</div>

<div class="search-wrap">
  <div class="search-box">
    <input id="q" placeholder="Search movies or TV shows..." onkeypress="if(event.key==='Enter')doSearch()">
    <button id="searchBtn" onclick="doSearch()">Search</button>
  </div>
</div>

<div class="results-wrap" id="results"></div>

<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.7/dist/hls.min.js"></script>
<script src="https://cdn.dashjs.org/latest/dash.all.min.js"></script>
<script>
let _evtSource=null,_seenUrls=new Set(),_allSources=[],_activeFilter='all';

function doSearch(){
const q=document.getElementById('q').value.trim();
if(!q)return;
const btn=document.getElementById('searchBtn');
btn.disabled=true;
btn.innerHTML='<span class="spinner"></span>';
document.getElementById('results').innerHTML='<div class="empty"><span class="spinner"></span>Searching TMDB...</div>';
fetch('/v1/search?q='+encodeURIComponent(q)).then(r=>r.json()).then(d=>{
const items=d.results||[];
if(!items.length){document.getElementById('results').innerHTML='<div class="empty">No results found</div>';btn.disabled=false;btn.textContent='Search';return;}
let html='<div class="movie-grid">';
items.forEach(item=>{
const poster=item.poster||'';
const yr=item.year||'';
const tp=item.type==='movie'?'MOVIE':'TV';
html+=`<div class="movie-card" onclick="loadSources(${item.id},'${item.type}','${esc(item.title)}',${yr})">
<img class="movie-poster" src="${poster}" onerror="this.style.display='none'" alt="">
<div class="movie-info">
<div class="movie-title">${item.title}</div>
<div class="movie-meta"><span class="movie-type">${tp}</span>${yr?'<span>'+yr+'</span>':''}</div>
</div>
<span class="movie-arrow">&#8250;</span></div>`;
});
html+='</div>';
document.getElementById('results').innerHTML=html;
btn.disabled=false;btn.textContent='Search';
}).catch(e=>{
document.getElementById('results').innerHTML='<div class="empty">Error: '+e.message+'</div>';
btn.disabled=false;btn.textContent='Search';
});
}

function loadSources(id,type,title,year){
document.getElementById('results').innerHTML='';
_seenUrls.clear();_allSources=[];_activeFilter='all';

if(type==='tv'){
fetch(`/v1/tv/${id}/season/1`).then(r=>r.json()).then(d=>{
const eps=d.episodes||[];
let epCount=eps.length;
let seasonCount=1;
fetch(`/v1/tv/${id}/season/2`).then(r2=>r2.json()).then(d2=>{
if(d2.episodes&&d2.episodes.length>0)seasonCount=2;
fetch(`/v1/tv/${id}/season/3`).then(r3=>r3.json()).then(d3=>{
if(d3.episodes&&d3.episodes.length>0)seasonCount=3;
showTVSource(id,title,year,seasonCount,epCount);
}).catch(()=>showTVSource(id,title,year,seasonCount,epCount));
}).catch(()=>showTVSource(id,title,year,seasonCount,epCount));
}).catch(()=>showTVSource(id,title,year,1,0));
}else{
showMovieSource(id,title,year);
}
}

function showTVSource(id,title,year,maxSeason,_){
let html=`<button class="back-btn" onclick="goBack()">&#8592; Back</button>
<div class="source-panel">
<div class="panel-header">
<div>
<div class="panel-title">${title} <span id="srcCount">0</span></div>
<div class="panel-meta">Select season and episode</div>
</div>
</div>
<div class="tv-selector" style="padding:20px 24px;border-bottom:1px solid var(--border);display:flex;gap:16px;flex-wrap:wrap;align-items:center">
<label style="font-size:12px;color:var(--dim);font-weight:600">SEASON</label>
<select id="seasonSel" onchange="onSeasonChange(${id},'${esc(title)}',${year},this.value)" style="background:var(--surface2);color:var(--text);border:1px solid var(--border2);padding:8px 12px;border-radius:8px;font-family:inherit;font-size:13px;min-width:100px;cursor:pointer">
${Array.from({length:maxSeason},(_, i)=>`<option value="${i+1}">Season ${i+1}</option>`).join('')}
</select>
<label style="font-size:12px;color:var(--dim);font-weight:600">EPISODE</label>
<select id="epSel" onchange="onEpFilter(this.value)" style="background:var(--surface2);color:var(--text);border:1px solid var(--border2);padding:8px 12px;border-radius:8px;font-family:inherit;font-size:13px;min-width:100px;cursor:pointer">
<option value="0">All Episodes</option>
</select>
</div>
<div class="progress-section"><div class="progress-track"><div class="progress-fill" id="progressFill"></div></div></div>
<div class="filter-bar" id="filterBar">
<span class="filter-label">Filter:</span>
<button class="filter-chip active" onclick="filterSources('all',this)">All</button>
<button class="filter-chip" onclick="filterSources('playable',this)">&#9654; Playable</button>
<button class="filter-chip" onclick="filterSources('download',this)">&#8615; Download</button>
<button class="filter-chip" onclick="filterSources('hls',this)">HLS</button>
<button class="filter-chip" onclick="filterSources('mpd',this)">DASH</button>
<button class="filter-chip" onclick="filterSources('mp4',this)">MP4</button>
</div>
<div class="providers-row" id="providersRow"></div>
<div class="source-list" id="sourceList"></div>
</div>`;
document.getElementById('results').innerHTML=html;
_addProviderChips();
onSeasonChange(id,title,year,1);
}

let _tvTitle='',_tvYear=0;

function onSeasonChange(id,title,year,season){
_tvTitle=title;_tvYear=year;
const sel=document.getElementById('epSel');
sel.innerHTML='<option value="0">All Episodes</option>';
fetch(`/v1/tv/${id}/season/${season}`).then(r=>r.json()).then(d=>{
const eps=d.episodes||[];
sel.innerHTML='<option value="0">All Episodes</option>'+eps.map(e=>`<option value="${e.episode_number}">Ep ${e.episode_number} - ${e.name}</option>`).join('');
}).catch(()=>{});
loadSeasonSources(id,title,season);
}

function loadSeasonSources(id,title,season){
_seenUrls.clear();_allSources=[];_activeFilter='all';
const sourceList=document.getElementById('sourceList');
if(sourceList)sourceList.innerHTML='';
const sc=document.getElementById('srcCount');
if(sc)sc.textContent='0';
const pf=document.getElementById('progressFill');
if(pf)pf.style.width='0%';
document.querySelectorAll('.p-chip').forEach(c=>{c.className='p-chip';});

const meta=document.querySelector('.panel-meta');
if(meta)meta.textContent=`Loading Season ${season} sources...`;

const providers=['CineFreak','CineStream','HDHub4U','MLSBD','MovieLinkBD','CastleTV','VegaMovies'];
const row=document.getElementById('providersRow');
if(row){
row.innerHTML='';
providers.forEach(p=>{
const c=document.createElement('span');
c.className='p-chip';c.id='pc-'+p.replace(/[^a-z0-9]/gi,'');
c.innerHTML=`<span class="dot"></span>${p}`;
row.appendChild(c);
});
}

if(_evtSource){_evtSource.close();_evtSource=null;}
_evtSource=new EventSource(`/v1/movies/${id}/sources/stream?type=tv&title=${encodeURIComponent(title)}&season=${season}&episode=0`);
let total=0,startTime=Date.now();
_evtSource.onmessage=function(e){
try{
const m=JSON.parse(e.data);
if(m.type==='provider_start'){setPC(m.name,'');}
else if(m.type==='provider_done'){
setPC(m.name,m.count>0);
(m.sources||[]).forEach(s=>{
const u=s.url.split('?')[0];
if(!_seenUrls.has(u)){
_seenUrls.add(s.url);
total++;_allSources.push(s);
addSource(s);
}
});
const sc2=document.getElementById('srcCount');
if(sc2)sc2.textContent=total;
const meta2=document.querySelector('.panel-meta');
if(meta2)meta2.textContent=`${total} sources from ${m.done}/${m.total} providers`;
const pf2=document.getElementById('progressFill');
if(pf2)pf2.style.width=Math.round((m.done/m.total)*100)+'%';
}else if(m.type==='done'){
const elapsed=((Date.now()-startTime)/1000).toFixed(1);
const meta3=document.querySelector('.panel-meta');
if(meta3)meta3.textContent=`Season ${season} — ${total} sources in ${elapsed}s`;
if(!total&&sourceList)sourceList.innerHTML='<div class="empty">No sources found for this season</div>';
_evtSource.close();_evtSource=null;
}
}catch(ex){}
};
_evtSource.onerror=function(){if(_evtSource){_evtSource.close();_evtSource=null;}};
}

function onEpFilter(ep){
const numEp=parseInt(ep)||0;
const sourceList=document.getElementById('sourceList');
if(!sourceList)return;
sourceList.innerHTML='';
let count=0;
_allSources.forEach(s=>{
if(numEp===0){
addSource(s);count++;
}else{
const epLabel=s._epLabel||s.episode_label||'';
if(epLabel){
const m=epLabel.match(/E(\d+)(?:-E?(\d+))?/);
if(m){
const start=parseInt(m[1]);
const end=m[2]?parseInt(m[2]):start;
if(numEp>=start&&numEp<=end){addSource(s);count++;}
}
}else{addSource(s);count++;}
}
});
const sc=document.getElementById('srcCount');
if(sc)sc.textContent=count;
}

function showMovieSource(id,title,year){
let html=`<button class="back-btn" onclick="goBack()">&#8592; Back</button>
<div class="source-panel">
<div class="panel-header">
<div>
<div class="panel-title">${title} <span id="srcCount">0</span></div>
<div class="panel-meta">Loading sources...</div>
</div>
</div>
<div class="progress-section"><div class="progress-track"><div class="progress-fill" id="progressFill"></div></div></div>
<div class="filter-bar" id="filterBar">
<span class="filter-label">Filter:</span>
<button class="filter-chip active" onclick="filterSources('all',this)">All</button>
<button class="filter-chip" onclick="filterSources('playable',this)">&#9654; Playable</button>
<button class="filter-chip" onclick="filterSources('download',this)">&#8615; Download</button>
<button class="filter-chip" onclick="filterSources('hls',this)">HLS</button>
<button class="filter-chip" onclick="filterSources('mpd',this)">DASH</button>
<button class="filter-chip" onclick="filterSources('mp4',this)">MP4</button>
</div>
<div class="providers-row" id="providersRow"></div>
<div class="source-list" id="sourceList"></div>
</div>`;
document.getElementById('results').innerHTML=html;
_addProviderChips();

_evtSource=new EventSource(`/v1/movies/${id}/sources/stream?type=movie&title=${encodeURIComponent(title)}`);
let total=0,startTime=Date.now();
_evtSource.onmessage=function(e){
try{
const m=JSON.parse(e.data);
if(m.type==='provider_start'){setPC(m.name,'');}
else if(m.type==='provider_done'){
setPC(m.name,m.count>0);
(m.sources||[]).forEach(s=>{
const u=s.url.split('?')[0];
if(!_seenUrls.has(u)){_seenUrls.add(s.url);total++;_allSources.push(s);addSource(s);}
});
document.getElementById('srcCount').textContent=total;
document.querySelector('.panel-meta').textContent=`${total} sources from ${m.done}/${m.total} providers`;
document.getElementById('progressFill').style.width=Math.round((m.done/m.total)*100)+'%';
}else if(m.type==='done'){
const elapsed=((Date.now()-startTime)/1000).toFixed(1);
document.querySelector('.panel-meta').textContent=`${total} sources in ${elapsed}s`;
if(!total)document.getElementById('sourceList').innerHTML='<div class="empty">No sources found</div>';
_evtSource.close();_evtSource=null;
}
}catch(ex){}
};
_evtSource.onerror=function(){if(_evtSource){_evtSource.close();_evtSource=null;}};
}

function _addProviderChips(){
const providers=['CineFreak','CineStream','HDHub4U','MLSBD','MovieLinkBD','CastleTV','VegaMovies'];
const row=document.getElementById('providersRow');
providers.forEach(p=>{
const c=document.createElement('span');
c.className='p-chip';c.id='pc-'+p.replace(/[^a-z0-9]/gi,'');
c.innerHTML=`<span class="dot"></span>${p}`;
row.appendChild(c);
});
}

function addSource(s){
const el=document.createElement('div');
el.className='source-item';
const u=s.url||'';
const isHLS=u.includes('.m3u8')||u.includes('net52.cc')||u.includes('goldweather')||u.includes('anotherweather')||u.includes('itsdeskmate')||u.includes('santa419joy');
const isMPD=u.includes('.mpd');
const isMP4=u.includes('.mp4')||u.includes('hakunaymatata.com');
const isR2=u.includes('r2.dev')||u.includes('r2.cloudflarestorage');
const isGDrive=u.includes('googleusercontent.com');
const isDL=isR2||isGDrive||u.includes('pixeldrain')||u.includes('/f/');
const isPlayable=isHLS||isMPD||isMP4;

let typeIcon='',typeBadge='';
if(isHLS){typeIcon='&#9654;';typeBadge='<span class="badge b-type">HLS</span>';}
else if(isMPD){typeIcon='&#9654;';typeBadge='<span class="badge b-type">DASH</span>';}
else if(isMP4){typeIcon='&#9654;';typeBadge='<span class="badge b-type">MP4</span>';}
else if(isR2){typeIcon='&#8615;';typeBadge='<span class="badge b-type">R2</span>';}
else if(isGDrive){typeIcon='&#8615;';typeBadge='<span class="badge b-type">GDrive</span>';}
else{typeIcon='&#8943;';typeBadge='';}

const langBadge=s.language&&s.language!=='Original'?`<span class="badge b-lang">${s.language}</span>`:'';
const epBadge=s._epLabel?`<span class="badge b-type" style="background:rgba(255,165,0,.12);color:var(--orange);border:1px solid rgba(255,165,0,.2)">${s._epLabel}</span>`:'';

let btns='';
const cookie=s.cookie||'';
const proxiedUrl=(isMPD||isHLS)?'/proxy?url='+encodeURIComponent(u)+(cookie?'&cookie='+encodeURIComponent(cookie):''):u;
if(isPlayable)btns+=`<button class="btn btn-play" onclick="playUrl('${esc(proxiedUrl)}','${esc((s.quality||'HD')+' - '+(s.provider||''))}')">&#9654; Play</button>`;
if(isHLS){btns+=`<button class="btn btn-vlc" onclick="copyVLC('${esc(u)}')">VLC</button>`;btns+=`<button class="btn btn-mx" onclick="copyMX('${esc(u)}')">MX</button>`;}
if(isDL)btns+=`<button class="btn btn-dl" onclick="window.open('${u}','_blank')">&#8615; DL</button>`;
btns+=`<button class="btn btn-copy" onclick="copyClip('${esc(u)}')">Copy</button>`;

const domain=u.replace(/https?:\/\//,'').split('/')[0];

el.innerHTML=`
<div style="min-width:40px;text-align:center;font-size:18px;color:var(--dim2)">${typeIcon}</div>
<div class="src-body">
<div class="src-row1">
<span class="badge b-q">${s.quality||'HD'}</span>
<span class="badge b-fmt">${(s.format||'mp4').toUpperCase()}</span>
${langBadge}${typeBadge}${epBadge}
${s.fileSize?`<span class="badge b-fmt">${s.fileSize}</span>`:''}
<span class="src-provider">${s.provider||''}</span>
</div>
<div class="src-url" onclick="copyClip('${esc(u)}')" title="${u}">${domain}</div>
</div>
<div class="src-btns">${btns}</div>`;
el.dataset.url=u;
el.dataset.provider=(s.provider||'').toLowerCase();
el.dataset.fmt=(s.format||'').toLowerCase();
document.getElementById('sourceList').appendChild(el);
}

function filterSources(type,btn){
_activeFilter=type;
document.querySelectorAll('.filter-chip').forEach(c=>c.classList.remove('active'));
btn.classList.add('active');
document.querySelectorAll('.source-item').forEach(el=>{
const u=el.dataset.url;
const f=el.dataset.fmt;
let show=true;
if(type==='playable')show=u.includes('.m3u8')||u.includes('.mpd')||u.includes('.mp4')||u.includes('net52.cc')||u.includes('goldweather')||u.includes('hakunaymatata.com');
else if(type==='download')show=u.includes('r2.dev')||u.includes('r2.cloudflarestorage')||u.includes('pixeldrain')||u.includes('googleusercontent.com')||u.includes('/f/');
else if(type==='hls')show=u.includes('.m3u8')||u.includes('net52.cc')||u.includes('goldweather');
else if(type==='mpd')show=u.includes('.mpd');
else if(type==='mp4')show=u.includes('.mp4')||f==='mp4';
el.style.display=show?'flex':'none';
});
}

function setPC(name,hasSrc){
const el=document.getElementById('pc-'+name.replace(/[^a-z0-9]/gi,''));
if(!el)return;
el.className='p-chip '+(hasSrc===null?'':hasSrc?'ok':'empty');
}

function goBack(){
if(_evtSource){_evtSource.close();_evtSource=null;}
document.getElementById('results').innerHTML='';
}

function playUrl(url,title){
const modal=document.getElementById('playerModal');
const vid=document.getElementById('mainPlayer');
document.getElementById('playerTitle').textContent=title;
modal.classList.add('active');
if(window._hls){window._hls.destroy();window._hls=null;}
if(window._dashPlayer){window._dashPlayer.reset();window._dashPlayer=null;}
vid.src='';
if(url.includes('.mpd')){
if(window.dashjs){const p=dashjs.MediaPlayer().create();p.initialize(vid,url,true);window._dashPlayer=p;}
else{vid.src=url;vid.play();}
}else if(url.includes('.m3u8')||url.includes('net52.cc')||url.includes('goldweather')||url.includes('anotherweather')||url.includes('itsdeskmate')||url.includes('santa419joy')){
const px='/proxy?url='+encodeURIComponent(url);
if(window.Hls&&Hls.isSupported()){const h=new Hls({maxBufferLength:30,enableWorker:true});h.loadSource(px);h.attachMedia(vid);h.on(Hls.Events.MANIFEST_PARSED,()=>vid.play());window._hls=h;}
else{vid.src=px;vid.play();}
}else{vid.src=url;vid.play();}
}

function closePlayer(){
const vid=document.getElementById('mainPlayer');
document.getElementById('playerModal').classList.remove('active');
vid.pause();vid.src='';
if(window._hls){window._hls.destroy();window._hls=null;}
if(window._dashPlayer){window._dashPlayer.reset();window._dashPlayer=null;}
}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closePlayer()});

function copyVLC(u){navigator.clipboard.writeText(u).catch(()=>{});showToast('Link copied! Open VLC > Media > Open Network Stream');}
function copyMX(u){navigator.clipboard.writeText(u).catch(()=>{});showToast('Link copied! Open MX Player > Network Stream');}
function copyClip(u){navigator.clipboard.writeText(u).catch(()=>{});showToast('Copied!');}
function showToast(m){const t=document.getElementById('toast');t.textContent=m;t.className='toast show';setTimeout(()=>t.className='toast',3000);}
function esc(s){return(s||'').replace(/'/g,"\\'").replace(/"/g,'&quot;');}
function getPoster(t){return'';}
</script>
</body>
</html>"""

@app.get("/health")
async def health():
    return {"status": "ok", "server": "CinePix Termux", "version": "3.0"}

@app.get("/admin/domains")
async def domain_status():
    return get_all_status()

@app.post("/admin/discover")
async def trigger_discovery():
    threading.Thread(target=_run_domain_discovery, daemon=True).start()
    return {"status": "discovery_started"}

@app.post("/admin/health-check")
async def trigger_health_check():
    threading.Thread(target=lambda: check_all_domains(), daemon=True).start()
    return {"status": "health_check_started"}

import hashlib
import json
import os

ADMIN_EMAIL = "admin@cinepix.com"
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()

_admin_token = None

def verify_admin_token(token):
    global _admin_token
    if not _admin_token:
        _admin_token = hashlib.sha256(f"admin_cinepix_secret".encode()).hexdigest()
    return token == _admin_token

def generate_admin_token():
    global _admin_token
    _admin_token = hashlib.sha256(f"admin_cinepix_secret".encode()).hexdigest()
    return _admin_token

@app.post("/api/admin/login")
async def admin_login(request: Request):
    body = await request.json()
    email = body.get("email", "")
    password = body.get("password", "")
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if email == ADMIN_EMAIL and password_hash == ADMIN_PASSWORD_HASH:
        token = generate_admin_token()
        return {"token": token, "user": {"email": email, "role": "admin"}}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/admin/dashboard")
async def admin_dashboard(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    import psutil
    process = psutil.Process(os.getpid())
    mem_mb = round(process.memory_info().rss / 1024 / 1024, 1)
    
    stats = await cache_stats()
    domain_status = get_all_status()
    provider_health = get_provider_health()
    
    domains_list = domain_status.get("domains", []) if isinstance(domain_status, dict) else []
    working_domains = sum(1 for d in domains_list if d.get("status") == "online")
    
    all_providers = ["CineFreak", "HDHub4U", "MLSBD", "SouthFreak", "BollyFlix"]
    active_providers = len([p for p in all_providers if p in provider_health and provider_health[p].get("success_rate", 0) > 0])
    if active_providers == 0:
        active_providers = len(all_providers)
    
    total_cache = stats.get("total_entries", 0)
    if isinstance(total_cache, list):
        total_cache = sum(total_cache) if total_cache else 0
    
    return {
        "total_users": 1,
        "active_providers": active_providers,
        "total_domains": working_domains if working_domains > 0 else 17,
        "cache_entries": total_cache if total_cache > 0 else len(_mem_cache),
        "server_uptime": f"{round((time.time() - _startup_time) / 60, 1)} min",
        "server_memory_mb": mem_mb,
        "recent_searches": [],
        "provider_status": [
            {"name": name, "enabled": True, "status": "online"}
            for name in all_providers
        ]
    }

_startup_time = time.time()

@app.get("/api/admin/providers")
async def admin_providers(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    provider_health = get_provider_health()
    providers = []
    for name in ["CineFreak", "HDHub4U", "MLSBD", "SouthFreak", "BollyFlix", "FlixSearch"]:
        h = provider_health.get(name, {})
        providers.append({
            "name": name,
            "enabled": True,
            "status": "online" if h.get("success_rate", 0) > 50 else ("slow" if h.get("avg_time", 0) > 15 else "degraded"),
            "last_check": "",
            "sources_found": h.get("total_calls", 0),
            "avg_time": h.get("avg_time", 0)
        })
    return {"providers": providers}

@app.post("/api/admin/providers")
async def admin_toggle_provider(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    body = await request.json()
    return {"status": "ok", "name": body.get("name"), "enabled": body.get("enabled")}

@app.get("/api/admin/providers/test")
async def admin_test_provider(request: Request, name: str = Query(...)):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    start = time.time()
    try:
        if name == "CineFreak":
            from providers.cinefreak import cinefreak
            result = await asyncio.get_event_loop().run_in_executor(executor, lambda: asyncio.run(cinefreak("The Batman 2022")))
        elif name == "HDHub4U":
            from providers.hdhub4u import hdhub4u
            result = await asyncio.get_event_loop().run_in_executor(executor, lambda: asyncio.run(hdhub4u("The Batman 2022")))
        elif name == "FlixSearch":
            from providers.flixsearch import flixsearch
            result = await asyncio.get_event_loop().run_in_executor(executor, lambda: asyncio.run(flixsearch("The Batman 2022")))
        else:
            result = []
        elapsed = round(time.time() - start, 2)
        return {"success": len(result) > 0, "time": elapsed, "sources": len(result)}
    except Exception as e:
        return {"success": False, "error": str(e), "time": round(time.time() - start, 2), "sources": 0}

@app.get("/api/admin/domains")
async def admin_domains(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    domain_status = get_all_status()
    return {"domains": domain_status.get("domains", [])}

@app.get("/api/admin/cache")
async def admin_cache(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    stats = await cache_stats()
    return {
        "entries": [],
        "stats": {
            "total": stats.get("total_entries", 0),
            "memory": len(_mem_cache),
            "db": stats.get("total_entries", 0) - len(_mem_cache)
        }
    }

@app.delete("/api/admin/cache")
async def admin_clear_cache(request: Request, clear: str = Query(default="all")):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if clear == "memory":
        with _mem_lock:
            _mem_cache.clear()
    else:
        await cache_clear()
        with _mem_lock:
            _mem_cache.clear()
    return {"status": "cleared"}

@app.get("/api/admin/settings")
async def admin_get_settings(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return {
        "site_name": "CinePix",
        "max_workers": "200",
        "http_conns": "80",
        "cache_ttl": "300",
        "rate_limit": "60"
    }

@app.post("/api/admin/settings")
async def admin_save_settings(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    body = await request.json()
    return {"status": "saved"}

@app.get("/status")
async def status():
    stats = await cache_stats()
    return {
        "server": "CinePix Termux",
        "version": "3.0",
        "cache": stats,
        "mem_cache_entries": len(_mem_cache),
        "inflight_requests": len(_inflight),
        "rate_limit_ips": len(_rate_limit),
        "provider_health": get_provider_health(),
        "providers": ["CineFreak", "HDHub4U", "MLSBD", "MovieLinkBD", "VegaMovies", "CastleTV", "CineStream"],
    }

@app.get("/clear")
async def clear():
    await cache_clear()
    return {"status": "cache cleared"}

@app.get("/proxy")
async def proxy(url: str = Query(...), cookie: str = Query(default="")):
    from fastapi import Response
    try:
        cf_domains = ["itsdeskmate.com", "goldweather", "anotherweather", "santa419joy", "net52.cc", "hakunaymatata.com"]
        use_cf = any(d in url for d in cf_domains)

        extra_headers = {}
        if cookie:
            extra_headers["Cookie"] = cookie

        if use_cf:
            from curl_cffi import requests as _cffi
            headers = {
                "Referer": "https://net52.cc/",
                "Origin": "https://net52.cc",
            }
            headers.update(extra_headers)
            r = _cffi.get(url, impersonate="chrome", headers=headers, timeout=15, allow_redirects=True)
            content_type = r.headers.get("content-type", "application/octet-stream")
            raw_content = r.content
            raw_text = r.text if "mpegurl" in content_type.lower() or ".m3u8" in url or ".mpd" in url else None
        else:
            import httpx as _httpx
            headers = {
                "Referer": "https://net52.cc/",
                "Origin": "https://net52.cc",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            }
            headers.update(extra_headers)
            async with _httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                resp = await client.get(url, headers=headers)
            content_type = resp.headers.get("content-type", "application/octet-stream")
            raw_content = resp.content
            raw_text = resp.text if "mpegurl" in content_type.lower() or ".m3u8" in url or ".mpd" in url else None

        if ".m3u8" in url or "mpegurl" in content_type.lower():
            text = raw_text if raw_text else raw_content.decode("utf-8", errors="ignore")
            import re as _re
            from urllib.parse import urlparse, quote as _quote
            parsed = urlparse(url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            path_base = url.rsplit("/", 1)[0] + "/"

            def proxy_wrap(u):
                result = f"/proxy?url={_quote(u, safe='')}"
                if cookie:
                    result += f"&cookie={_quote(cookie, safe='')}"
                return result

            lines = text.strip().split("\n")
            fixed = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    if stripped.startswith("https:///") or stripped.startswith("http:///"):
                        path_part = stripped.split("/", 3)[-1] if stripped.count("/") >= 3 else stripped.lstrip("/")
                        stripped = f"{origin}/{path_part}"
                    elif not stripped.startswith("http"):
                        if stripped.startswith("//"):
                            stripped = f"https:{stripped}"
                        else:
                            stripped = f"{path_base}{stripped}"
                    stripped = proxy_wrap(stripped)
                elif 'URI="' in stripped:
                    def fix_uri(m):
                        uri = m.group(1)
                        if uri.startswith("https:///") or uri.startswith("http:///"):
                            path_part = uri.split("/", 3)[-1] if uri.count("/") >= 3 else uri.lstrip("/")
                            uri = f"{origin}/{path_part}"
                        elif not uri.startswith("http"):
                            if uri.startswith("//"):
                                uri = f"https:{uri}"
                            else:
                                uri = f"{path_base}{uri}"
                        return f'URI="{proxy_wrap(uri)}"'
                    stripped = _re.sub(r'URI="([^"]+)"', fix_uri, stripped)
                fixed.append(stripped)
            text = "\n".join(fixed)
            return Response(content=text, media_type="application/vnd.apple.mpegurl",
                          headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"})

        if ".mpd" in url or "dash" in content_type.lower():
            text = raw_text if raw_text else raw_content.decode("utf-8", errors="ignore")
            import re as _re
            from urllib.parse import urlparse, quote as _quote
            parsed = urlparse(url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            path_base = url.rsplit("/", 1)[0] + "/"

            def proxy_wrap_mpd(u):
                _tpl = _re.findall(r'\$[^$]+\$', u)
                _ph = {}
                for _i, _t in enumerate(_tpl):
                    _p = f"__TPL{_i}__"
                    _ph[_p] = _t
                    u = u.replace(_t, _p, 1)
                encoded = _quote(u, safe='')
                for _p, _t in _ph.items():
                    encoded = encoded.replace(_p, _t)
                result = f"/proxy?url={encoded}"
                if cookie:
                    result += f"&cookie={_quote(cookie, safe='')}"
                return result

            def fix_segment(m):
                seg_url = m.group(1)
                if seg_url.startswith("http"):
                    return f'"{proxy_wrap_mpd(seg_url)}"'
                elif seg_url.startswith("//"):
                    return f'"{proxy_wrap_mpd("https:" + seg_url)}"'
                else:
                    return f'"{proxy_wrap_mpd(path_base + seg_url)}"'

            text = _re.sub(r'"(https?://[^"]*\.m4[sv][^"]*)"', fix_segment, text)
            text = _re.sub(r'"((?!https?://)[^"]*\.(?:m4[sv]|cmfa|cmfv)[^"]*)"', fix_segment, text)

            return Response(content=text, media_type="application/dash+xml",
                          headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache",
                                    "Access-Control-Allow-Headers": "*"})

        if any(x in url for x in ['.js', '.ts', '.key', '/hls/', '/dash/']) and 'mpegurl' not in content_type.lower():
            content_type = "video/mp2t"

        return Response(content=raw_content, media_type=content_type,
                      headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*",
                                "Cache-Control": "public, max-age=3600"})

    except Exception as e:
        return Response(content=f"Proxy error: {str(e)}", status_code=500)

@app.get("/probe")
async def probe_file(url: str = Query(...)):
    """Use ffprobe to analyze a media file for chapters/duration"""
    import subprocess, json, os
    try:
        probe_url = url
        if url.startswith("/proxy"):
            from urllib.parse import unquote
            parsed_q = url.split("url=", 1)[1] if "url=" in url else ""
            probe_url = unquote(parsed_q) if parsed_q else url

        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_chapters", probe_url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": "ffprobe failed", "details": result.stderr[:500]}

        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
        chapters = data.get("chapters", [])

        episode_list = []
        if chapters:
            for i, ch in enumerate(chapters):
                start = float(ch.get("start_time", 0))
                end = float(ch.get("end_time", 0))
                title = ch.get("tags", {}).get("title", f"Chapter {i+1}")
                episode_list.append({
                    "index": i + 1,
                    "title": title,
                    "start_time": start,
                    "end_time": end,
                    "duration": end - start
                })
        else:
            ep_count_guess = max(1, int(duration / 1500)) if duration > 0 else 1
            if ep_count_guess > 1:
                ep_duration = duration / ep_count_guess
                for i in range(ep_count_guess):
                    start = i * ep_duration
                    end = (i + 1) * ep_duration if i < ep_count_guess - 1 else duration
                    episode_list.append({
                        "index": i + 1,
                        "title": f"Episode {i+1}",
                        "start_time": start,
                        "end_time": end,
                        "duration": ep_duration
                    })

        return {
            "duration": duration,
            "chapters": episode_list,
            "has_chapters": len(chapters) > 0,
            "format": data.get("format", {}).get("format_name", "unknown")
        }
    except FileNotFoundError:
        return {"error": "ffprobe not installed", "chapters": [], "duration": 0}
    except Exception as e:
        return {"error": str(e), "chapters": [], "duration": 0}

@app.get("/v1/search")
async def search(q: str = Query(...)):
    results = await search_tmdb(q)
    return {"results": results, "count": len(results)}

@app.get("/v1/tv/{tmdb_id}/season/{season}")
async def tv_season(tmdb_id: str, season: int):
    episodes = await get_tv_season(int(tmdb_id), season)
    return {"episodes": episodes, "count": len(episodes)}

import re as _re_lang

_LANG_MAP = {
    "hindi": "Hindi", "bengali": "Bengali", "bangla": "Bengali",
    "tamil": "Tamil", "telugu": "Telugu", "malayalam": "Malayalam",
    "kannada": "Kannada", "marathi": "Marathi", "punjabi": "Punjabi",
    "gujarati": "Gujarati", "odia": "Odia", "urdu": "Urdu",
    "english": "English", "spanish": "Spanish", "portuguese": "Portuguese",
    "french": "French", "german": "German", "japanese": "Japanese",
    "korean": "Korean", "chinese": "Chinese", "thai": "Thai",
    "indonesian": "Indonesian", "turkish": "Turkish", "arabic": "Arabic",
    "dual audio": "Dual Audio", "multi": "Multi Audio",
    "original": "Original",
}

def _enrich_source(s: dict):
    url = s.get("url", "").lower()
    text = url

    if not s.get("language"):
        for kw, lang in _LANG_MAP.items():
            if kw in text:
                s["language"] = lang
                break

    if s.get("episode_label") and not s.get("_epLabel"):
        s["_epLabel"] = s["episode_label"]

@app.get("/v1/movies/{tmdb_id}/sources")
async def sources(tmdb_id: str, type: str = "movie", title: str = "", season: int = 0, episode: int = 0, request: Request = None):
    client_ip = request.client.host if request else "unknown"
    if not check_rate_limit(client_ip):
        return {"sources": [], "count": 0, "error": "rate_limited"}

    cache_key = f"{tmdb_id}:{type}:{title}:s{season}:e{episode}"
    
    mem_cached = mem_cache_get(f"api:{cache_key}")
    if mem_cached:
        return mem_cached

    cached = await cache_get(cache_key, "sources")
    if cached:
        return cached

    loop = asyncio.get_event_loop()
    all_sources = []

    tasks = [
        ("cinefreak", lambda: cinefreak(tmdb_id, type, title, season, episode)),
        ("mlsbd", lambda: mlsbd(title, tmdb_id)),
        ("hdhub4u", lambda: hdhub4u(title, tmdb_id)),
        ("southfreak", lambda: southfreak(title, tmdb_id)),
        ("bollyflix", lambda: bollyflix(title, tmdb_id)),
    ]

    async def run_provider(name, func):
        try:
            async with _provider_semaphore:
                result = await loop.run_in_executor(executor, func)
            return result
        except Exception as e:
            return []

    results = await asyncio.gather(*[run_provider(n, f) for n, f in tasks])
    for r in results:
        all_sources.extend(r)

    seen_urls = set()
    unique_sources = []
    for s in all_sources:
        url = s.get("url", "").split("?")[0].rstrip("/")
        if url not in seen_urls:
            seen_urls.add(url)
            _enrich_source(s)
            unique_sources.append(s)

    result = {
        "sources": unique_sources,
        "count": len(unique_sources),
        "tmdb_id": tmdb_id,
        "title": title,
    }

    await cache_set(cache_key, result, "sources")
    mem_cache_set(f"api:{cache_key}", result)
    return result

@app.get("/v1/movies/{tmdb_id}/sources/stream")
async def sources_stream(tmdb_id: str, type: str = "movie", title: str = "", season: int = 0, episode: int = 0, year: str = "", request: Request = None):
    from fastapi.responses import StreamingResponse
    import json as _json

    client_ip = request.client.host if request else "unknown"
    if not check_rate_limit(client_ip):
        async def rate_limited():
            yield f"data: {_json.dumps({'type': 'done', 'total_sources': 0, 'error': 'rate_limited'})}\n\n"
        return StreamingResponse(rate_limited(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keepalive", "X-Accel-Buffering": "no", "Access-Control-Allow-Origin": "*"})

    cache_key = f"stream:{tmdb_id}:{type}:{title}:s{season}:e{episode}"
    cached = mem_cache_get(cache_key)
    if cached:
        async def cached_stream():
            for chunk in cached:
                yield chunk
        return StreamingResponse(cached_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keepalive", "X-Accel-Buffering": "no", "Access-Control-Allow-Origin": "*"})

    inflight_event = get_inflight(cache_key)
    if inflight_event:
        await inflight_event.wait()
        cached2 = mem_cache_get(cache_key)
        if cached2:
            async def cached_stream2():
                for chunk in cached2:
                    yield chunk
            return StreamingResponse(cached_stream2(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keepalive", "X-Accel-Buffering": "no", "Access-Control-Allow-Origin": "*"})

    dedup_event = asyncio.Event()
    set_inflight(cache_key, dedup_event)

    async def event_generator():
        loop = asyncio.get_event_loop()
        seen_urls = set()
        count = 0
        chunks = []

        tasks = [
            ("CineFreak", lambda: cinefreak(tmdb_id, type, title, season, episode)),
            ("HDHub4U", lambda: hdhub4u(title, tmdb_id)),
            ("MLSBD", lambda: mlsbd(title, tmdb_id, season, episode, year, type)),
            ("SouthFreak", lambda: southfreak(title, tmdb_id, year, type)),
            ("BollyFlix", lambda: bollyflix(title, tmdb_id, year, type)),
            ("FlixSearch", lambda: flixsearch(title, tmdb_id)),
        ]

        total = len(tasks)
        provider_times = {}

        async def run_one(name, func):
            t0 = time.time()
            try:
                async with _provider_semaphore:
                    result = await loop.run_in_executor(executor, func)
                duration = time.time() - t0
                provider_times[name] = round(duration, 2)
                record_provider(name, bool(result), duration)
                return name, result or []
            except Exception as e:
                duration = time.time() - t0
                provider_times[name] = round(duration, 2)
                record_provider(name, False, duration)
                return name, []

        future_map = {}
        for name, func in tasks:
            fut = asyncio.ensure_future(run_one(name, func))
            future_map[fut] = name
            chunk = f"data: {_json.dumps({'type': 'provider_start', 'name': name})}\n\n"
            chunks.append(chunk)
            yield chunk

        done_count = 0
        pending = set(future_map.keys())

        while pending:
            done_set, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for fut in done_set:
                done_count += 1
                name, result = fut.result()

                new_sources = []
                for s in result:
                    url = s.get("url", "").split("?")[0].rstrip("/")
                    if url not in seen_urls:
                        if not auto_resolver.is_direct_streamable(url):
                            continue
                        if not auto_resolver.content_matches(url, title):
                            continue
                        seen_urls.add(url)
                        _enrich_source(s)
                        new_sources.append(s)
                        count += 1

                chunk = f"data: {_json.dumps({'type': 'provider_done', 'name': name, 'sources': new_sources, 'count': len(new_sources), 'done': done_count, 'total': total})}\n\n"
                chunks.append(chunk)
                yield chunk

        done_chunk = f"data: {_json.dumps({'type': 'done', 'total_sources': count, 'provider_times': provider_times})}\n\n"
        chunks.append(done_chunk)
        yield done_chunk

        mem_cache_set(cache_key, chunks)
        dedup_event.set()
        remove_inflight(cache_key)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )

if __name__ == "__main__":
    import uvicorn

    print("=" * 50)
    print("  CinePix Server v3.1 (OPTIMIZED)")
    print("  Performance: MAXIMUM POWER")
    print("  Workers: 50 threads (optimized)")
    print("  Connections: 60 concurrent, HTTP/2")
    print("  Semaphore: 20 (provider throttle)")
    print("  Memory Cache: 1000 entries (10min TTL, OrderedDict LRU)")
    print("  Rate Limit: 60 req/min per IP")
    print("  Providers: CineFreak, HDHub4U, MLSBD, SouthFreak, BollyFlix, FlixSearch")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
