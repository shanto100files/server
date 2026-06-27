import re, json, base64, time
import asyncio
from urllib.parse import unquote
from bs4 import BeautifulSoup
from client import async_cf_get, async_cf_post

VEGAMOVIES_DOMAINS = ["https://vegamovies4u.co.in", "https://vegamovies.mq", "https://vegamovies.market", "https://vegamovies.tel", "https://vegamovie.sl"]
DYNAMIC_URLS = "https://raw.githubusercontent.com/SaurabhKaperwan/Utils/refs/heads/main/urls.json"

_DOMAIN_CACHE = {"url": None, "time": 0}
_DOMAIN_CACHE_TTL = 3600  # 1 hour


async def _fetch(url, timeout=12):
    return await async_cf_get(url, headers={"Referer": "https://vegamovies4u.co.in"}, timeout=timeout)

async def _dle_search(domain, query, timeout=12):
    """DLE CMS search via POST form submission"""
    body = f"do=search&subaction=search&story={query}"
    resp = await async_cf_post(domain + "/", data=body, headers={
        "Referer": domain + "/",
        "Content-Type": "application/x-www-form-urlencoded",
    }, timeout=timeout)
    if not resp:
        return None
    return resp.text if hasattr(resp, 'text') else resp

async def _get_domain():
    global _DOMAIN_CACHE
    if _DOMAIN_CACHE["url"] and (time.time() - _DOMAIN_CACHE["time"] < _DOMAIN_CACHE_TTL):
        return _DOMAIN_CACHE["url"]
        
    try:
        r = await async_cf_get(DYNAMIC_URLS, timeout=8)
        if r:
            data = json.loads(r)
            domain = data.get("vegamovies", VEGAMOVIES_DOMAINS[0])
            _DOMAIN_CACHE["url"] = domain
            _DOMAIN_CACHE["time"] = time.time()
            return domain
    except:
        pass
        
    if _DOMAIN_CACHE["url"]:
        return _DOMAIN_CACHE["url"]
    return VEGAMOVIES_DOMAINS[0]

async def _resolve_vcloud(url):
    html = await _fetch(url, timeout=10)
    if not html:
        return []
    m = re.search(r'var\s+url\s*=\s*atob\(atob\(["\']([^"\']+)["\']\)\)', html)
    if not m:
        return []
    b64 = m.group(1)
    while len(b64) % 4 != 0:
        b64 += "="
    try:
        once = base64.b64decode(b64).decode()
        while len(once) % 4 != 0:
            once += "="
        token_url = base64.b64decode(once).decode()
    except:
        return []
    token_html = await _fetch(token_url, timeout=10)
    if not token_html:
        return []
    results = []
    soup = BeautifulSoup(token_html, "html.parser")
    for h2 in soup.find_all("h2"):
        for a in h2.find_all_next("a", href=True):
            h = a["href"]
            t = a.get_text(strip=True)
            if not h.startswith("http"):
                continue
            if any(x in h for x in [".css", ".js", "fonts", "favicon"]):
                continue
            quality = "HD"
            combined = t + " " + unquote(h)
            for q in ["2160p", "4K", "1080p", "720p", "480p"]:
                if q.lower() in combined.lower():
                    quality = q
                    break
            if "FSLv2" in t or "FSL" in t or "10Gbps" in t or "Mega" in t or "Buzz" in t or "Pixeldrain" in t:
                results.append({"url": h, "quality": quality})
                if len(results) >= 6:
                    break
        if results:
            break
    return results

async def vegamovies(title, tmdb_id="", season=0, episode=0, year="", media_type=""):
    domain = await _get_domain()
    # DLE CMS search via POST
    html = await _dle_search(domain, title, timeout=12)
    if not html:
        return []
    # Parse DLE search results HTML
    soup = BeautifulSoup(html, "html.parser")
    post_url = None
    qw = set(title.lower().split())
    # Find search result entries
    for article in soup.find_all(["article", "div", "h2", "h3"], class_=re.compile(r"post|entry|item|result", re.I)):
        a_tag = article.find("a", href=True)
        if not a_tag:
            continue
        href = a_tag["href"]
        post_title = a_tag.get_text(strip=True)
        if not href.startswith("http"):
            href = domain + href
        pt_lower = post_title.lower()
        tw = set(pt_lower.split())
        overlap = qw & tw
        if not overlap:
            continue
        precision = len(overlap) / len(qw) if qw else 0
        if precision < 0.5:
            continue
        if year and year not in post_title:
            continue
        post_url = href
        break
    # Fallback: try any <a> with href ending in .html
    if not post_url:
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            post_title = a_tag.get_text(strip=True)
            if not href.endswith(".html"):
                continue
            if not href.startswith("http"):
                href = domain + href
            pt_lower = post_title.lower()
            tw = set(pt_lower.split())
            overlap = qw & tw
            if not overlap:
                continue
            precision = len(overlap) / len(qw) if qw else 0
            if precision < 0.5:
                continue
            if year and year not in post_title:
                continue
            post_url = href
            break
    if not post_url:
        return []
    post_html = await _fetch(post_url, timeout=12)
    if not post_html:
        return []
    soup = BeautifulSoup(post_html, "html.parser")
    final = []
    seen = set()
    for a in soup.find_all("a", href=True):
        h = a["href"]
        t = a.get_text(strip=True)
        if not h or "#" in h or not h.startswith("http"):
            continue
        if "nexdrive" not in h:
            continue
        nex_html = await _fetch(h, timeout=10)
        if not nex_html:
            continue
        vcloud_url = None
        for m in re.finditer(r'href="(https?://vcloud\.zip/[^"]*)"', nex_html):
            vcloud_url = m.group(1)
            break
        if not vcloud_url:
            for m in re.finditer(r'href="(https?://[^"]*(?:hubcloud|vcloud)[^"]*)"', nex_html):
                hh = m.group(1)
                if "signup" not in hh and "tg/" not in hh and "bit.ly" not in hh:
                    vcloud_url = hh
                    break
        if not vcloud_url:
            continue
        resolved = await _resolve_vcloud(vcloud_url)
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
            final.append({"url": url, "quality": quality, "provider": "VegaMovies", "format": fmt})
    return final[:10]
