import re
import time
from urllib.parse import unquote
from bs4 import BeautifulSoup
from client import async_cf_get

DOMAINS = ["https://4khdhub.one", "https://4khdhub.link", "https://4khdhub.net"]
DYNAMIC_URLS = "https://raw.githubusercontent.com/SaurabhKaperwan/Utils/refs/heads/main/urls.json"

_DOMAIN_CACHE = {"url": None, "time": 0}
_DOMAIN_CACHE_TTL = 3600  # 1 hour


async def _fetch(url, timeout=12, headers=None):
    hdrs = {"Referer": "https://4khdhub.one"}
    if headers:
        hdrs.update(headers)
    return await async_cf_get(url, headers=hdrs, timeout=timeout)

async def _get_domain():
    global _DOMAIN_CACHE
    if _DOMAIN_CACHE["url"] and (time.time() - _DOMAIN_CACHE["time"] < _DOMAIN_CACHE_TTL):
        return _DOMAIN_CACHE["url"]

    try:
        r = await async_cf_get(DYNAMIC_URLS, timeout=8)
        if r:
            import json
            domain = json.loads(r).get("4khdhub", DOMAINS[0])
            _DOMAIN_CACHE["url"] = domain
            _DOMAIN_CACHE["time"] = time.time()
            return domain
    except:
        pass
        
    if _DOMAIN_CACHE["url"]:
        return _DOMAIN_CACHE["url"]
    return DOMAINS[0]

async def _resolve_hubcloud(hub_url):
    html = await _fetch(hub_url, timeout=10)
    if not html:
        return []
    m = re.search(r"var url = '([^']+)'", html)
    if not m:
        return []
    redirect = m.group(1)
    r = await async_cf_get(redirect, headers={"Cookie": "xla=s4t", "Referer": hub_url}, timeout=10)
    if not r:
        return []
    results = []
    soup = BeautifulSoup(r, "lxml")
    for a in soup.find_all("a", href=True):
        h = a["href"]
        t = a.get_text(strip=True)
        if not h.startswith("http"):
            continue
        if any(x in h for x in [".css", ".js", "cdn.", "fonts", "unpkg", "use.fontawesome", "favicon"]):
            continue
        combined = (t + " " + unquote(h)).lower()
        if not any(x in combined for x in ["fsl", "server", "download", "s3", "mega", "buzz", "pixel", "zip", "10gbps", "gpdl"]):
            continue
        quality = "HD"
        for q in ["2160p", "4K", "1080p", "720p", "480p"]:
            if q.lower() in combined:
                quality = q
                break
        results.append({"url": h, "quality": quality})
    return results

async def fourkhd(title, tmdb_id="", season=0, episode=0, year="", media_type=""):
    domain = await _get_domain()
    html = await _fetch(f"{domain}/?s={title}", timeout=10)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    qw = set(title.lower().split())
    post_url = None
    best_score = 0
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if not h.startswith("/") or "/?s=" in h:
            continue
        if not re.search(r"(movie|series)-\d+/", h):
            continue
        slug = h.rstrip("/").split("/")[-1]
        slug_words = set(re.sub(r"-\d+$", "", slug).replace("-", " ").split())
        overlap = qw & slug_words
        if overlap:
            score = len(overlap) / len(qw) * 100
            if score > best_score:
                best_score = score
                post_url = h
    if not post_url:
        return []
    post_html = await _fetch(domain + post_url, timeout=12)
    if not post_html:
        return []
    soup = BeautifulSoup(post_html, "lxml")
    seen = set()
    final = []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if "hubcloud" not in h:
            continue
        if h in seen:
            continue
        seen.add(h)
        resolved = await _resolve_hubcloud(h)
        for r in resolved:
            url = r["url"]
            if url in seen:
                continue
            seen.add(url)
            quality = r.get("quality", "HD")
            for q in ["2160p", "4K", "1080p", "720p", "480p"]:
                if q.lower() in url.lower():
                    quality = q
                    break
            fmt = "mkv" if ".mkv" in url else "mp4"
            final.append({"url": url, "quality": quality, "provider": "4KHD", "format": fmt})
    return final[:10]
