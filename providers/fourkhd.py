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
    
    # Extract metadata from hubcloud page
    meta = {}
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    if title_tag:
        meta["filename"] = title_tag.get_text(strip=True)
    for li in soup.find_all("li"):
        text = li.get_text(strip=True)
        if "File Size" in text:
            sz = li.find("i")
            if sz:
                meta["fileSize"] = sz.get_text(strip=True)
        elif "File Type" in text:
            ft = li.find("i")
            if ft:
                meta["fileType"] = ft.get_text(strip=True)
    
    m = re.search(r"var url = '([^']+)'", html)
    if not m:
        return []
    redirect = m.group(1)
    r = await async_cf_get(redirect, headers={"Cookie": "xla=s4t", "Referer": hub_url}, timeout=10)
    if not r:
        return []
    results = []
    soup2 = BeautifulSoup(r, "html.parser")
    for a in soup2.find_all("a", href=True):
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
        entry = {"url": h, "quality": quality}
        if meta:
            entry["metadata"] = meta
        results.append(entry)
    return results

async def fourkhd(title, tmdb_id="", season=0, episode=0, year="", media_type=""):
    # Check pre-scraped data first
    from providers.hdhub4k_scraper import search_pre_scraped
    pre_scraped = await search_pre_scraped(title)
    if pre_scraped:
        results = []
        for post in pre_scraped[:3]:
            for link in post.get("download_links", []):
                results.append({
                    "url": link["url"],
                    "quality": "HD",
                    "provider": "4KHDHub",
                    "source": "pre-scraped"
                })
        if results:
            return results

    domain = await _get_domain()
    qw = set(title.lower().split())
    post_url = None

    html = await _fetch(f"{domain}/?s={title}", timeout=10)
    if html:
        soup = BeautifulSoup(html, "html.parser")
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
                post_url = h
                break

    if not post_url:
        q_plus = title.replace(" ", "+")
        dle_html = await _fetch(f"{domain}/?do=search&subaction=search&story={q_plus}", timeout=10)
        if dle_html:
            soup = BeautifulSoup(dle_html, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if not re.search(r"(movie|series)-\d+/", href):
                    continue
                slug = href.rstrip("/").split("/")[-1]
                slug_words = set(re.sub(r"-\d+$", "", slug).replace("-", " ").split())
                overlap = qw & slug_words
                if overlap:
                    post_url = href
                    break

    if not post_url:
        return []
    post_html = await _fetch(domain + post_url, timeout=12)
    if not post_html:
        return []
    soup = BeautifulSoup(post_html, "html.parser")
    seen = set()
    final = []
    from providers.auto_resolver import resolve_any, is_direct_streamable
    for a in soup.find_all("a", href=True):
        h = a["href"]
        t = a.get_text(strip=True)
        if not h.startswith("http"):
            continue
        if any(x in h for x in [".css", ".js", "cdn.", "fonts"]):
            continue
        if h in seen:
            continue
        if not any(x in h for x in ["hubcloud", "gdflix", "drivebot", "hubdrive", "fast-dl", "nexdrive"]):
            continue
        seen.add(h)
        quality = "HD"
        combined = (t + " " + unquote(h)).lower()
        for q in ["2160p", "4K", "1080p", "720p", "480p"]:
            if q.lower() in combined:
                quality = q
                break
        try:
            resolved = await asyncio.to_thread(resolve_any, h, quality, post_url)
            if resolved:
                for r in resolved:
                    url = r["url"]
                    if url in seen:
                        continue
                    seen.add(url)
                    entry = {"url": url, "quality": r.get("quality", quality), "provider": "4KHD", "format": "zip" if ".zip" in url else ("mkv" if ".mkv" in url else "mp4")}
                    meta = r.get("metadata")
                    if meta:
                        if meta.get("fileSize"):
                            entry["fileSize"] = meta["fileSize"]
                        if meta.get("filename"):
                            entry["filename"] = meta["filename"]
                        if meta.get("fileType"):
                            entry["fileType"] = meta["fileType"]
                    final.append(entry)
            elif h not in seen:
                fmt = "zip" if ".zip" in h else ("mkv" if ".mkv" in h else "mp4")
                final.append({"url": h, "quality": quality, "provider": "4KHD", "format": fmt})
        except Exception:
            pass
    return final[:10]
