import re
import time
import threading
import asyncio
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
from client import async_cf_get
from providers.hubcloud import extract_hubcloud
from providers.gdflix import resolve_gdflix
from providers.hubdrive import resolve_hubdrive

HDHUB4U_DOMAINS = ["https://new2.hdhub4u.limo", "https://new2.hdhub4u.cl"]
_PRIMARY = HDHUB4U_DOMAINS[0]

_sitemap_cache: dict[str, list[str]] = {"urls": [], "ts": 0}
_sitemap_lock = threading.Lock()
_SITEMAP_TTL = 3600


async def _load_sitemap() -> list[str]:
    now = time.time()
    with _sitemap_lock:
        if _sitemap_cache["urls"] and now - _sitemap_cache["ts"] < _SITEMAP_TTL:
            return _sitemap_cache["urls"]

    urls = []
    for domain in HDHUB4U_DOMAINS:
        try:
            index_r = await async_cf_get(f"{domain}/sitemap.xml", timeout=12)
            if not index_r:
                continue
            soup = BeautifulSoup(index_r, "html.parser")
            post_sitemaps = [loc.text for loc in soup.find_all("loc") if "post-sitemap" in loc.text]
            for sm_url in post_sitemaps:
                sm_html = await async_cf_get(sm_url, timeout=12)
                if sm_html:
                    sm_soup = BeautifulSoup(sm_html, "html.parser")
                    urls.extend(loc.text for loc in sm_soup.find_all("loc"))
            if urls:
                break
        except Exception:
            continue

    if urls:
        with _sitemap_lock:
            _sitemap_cache["urls"] = urls
            _sitemap_cache["ts"] = time.time()

    return urls


def _slug_match(query: str, url: str) -> float:
    slug = url.rstrip("/").split("/")[-1]
    slug_clean = re.sub(
        r"-(1080p|720p|480p|4k|2160p|bluray|web-dl|webrip|dvdrip|hdtv|hdcam|cam|pdvdrip|hdrip|hevc|x264|x265|10bit|full|movie|hindi|english|dual.?audio|south|hollywood|bollywood|uncut|extended|proper|amzn|nf|hotstar|jio|zee5|sony.?liv|mx.?player|telegram|hdrip|pre.?dvd|hdcam|camrip|ts|dvdscr|scr).*",
        "",
        slug,
        flags=re.I,
    )
    year_match = re.search(r"(\d{4})", slug_clean)
    slug_title = re.sub(r"-\d{4}(-|$)", "", slug_clean).replace("-", " ").strip().lower()
    q = query.lower().strip()

    if q == slug_title:
        return 100.0

    qw = set(q.split())
    sw = set(slug_title.split())
    qw.discard("")
    sw.discard("")
    if not qw or not sw:
        return 0.0

    overlap = qw & sw
    if not overlap:
        return 0.0

    precision = len(overlap) / len(qw)
    recall = len(overlap) / len(sw)
    score = precision * 60 + recall * 40

    if len(overlap) == len(qw) and len(overlap) == len(sw):
        score = 99.0
    elif len(overlap) == len(qw):
        score = max(score, 85.0)

    if year_match:
        score += 5

    return min(score, 99.5)


async def _search_sitemap(title: str) -> str | None:
    urls = await _load_sitemap()
    if not urls:
        return None

    scored = []
    for url in urls:
        score = _slug_match(title, url)
        if score >= 30:
            scored.append((score, url))
    scored.sort(reverse=True)

    if scored:
        return scored[0][1]
    return None


async def _search_direct(title: str) -> str | None:
    return await _search_sitemap(title)


async def hdhub4u(title: str, tmdb_id: str = "") -> list[dict]:
    sources = []
    loop = asyncio.get_event_loop()

    permalink = await _search_sitemap(title)
    if not permalink:
        permalink = await _search_direct(title)
    if not permalink:
        return sources

    post_url = None
    for domain in HDHUB4U_DOMAINS:
        test_url = f"{domain}{permalink}" if permalink.startswith("/") else permalink
        if not test_url.startswith("http"):
            test_url = f"{domain}/{test_url}"
        try:
            r_html = await async_cf_get(test_url, timeout=10)
            if r_html and len(r_html) > 1000:
                post_url = test_url
                break
        except Exception:
            continue

    if not post_url:
        return sources

    post_html = await async_cf_get(post_url, timeout=10)
    if not post_html:
        return sources

    soup = BeautifulSoup(post_html, "html.parser")

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if not href:
            continue

        quality = _extract_quality(text)

        if any(x in href for x in ["hubcloud", "gdflix"]):
            if "gdflix" in href:
                gdflix_resolved = await loop.run_in_executor(None, lambda: resolve_gdflix(href, quality=quality, referer=post_url))
                if gdflix_resolved:
                    for g in gdflix_resolved:
                        sources.append(g)
                else:
                    sources.append({
                        "url": href,
                        "quality": quality,
                        "provider": "HDHub4U",
                        "format": "mkv" if "mkv" in text.lower() else "mp4",
                    })
            else:
                resolved = await loop.run_in_executor(None, lambda: extract_hubcloud(href, quality=quality, referer=post_url))
                if resolved:
                    for r in resolved:
                        sources.append(r)
                else:
                    sources.append({
                        "url": href,
                        "quality": quality,
                        "provider": "HDHub4U",
                        "format": "mkv" if "mkv" in text.lower() else "mp4",
                    })
        elif any(x in href for x in ["hubdrive", "filepress"]):
            if "hubdrive" in href:
                hub_resolved = await loop.run_in_executor(None, lambda: resolve_hubdrive(href))
                if hub_resolved:
                    for hr in hub_resolved:
                        sources.append(hr)
                else:
                    sources.append({
                        "url": href,
                        "quality": quality,
                        "provider": "HDHub4U",
                        "format": "mkv" if "mkv" in text.lower() else "mp4",
                    })
            else:
                sources.append({
                    "url": href,
                    "quality": quality,
                    "provider": "HDHub4U",
                    "format": "mkv" if "mkv" in text.lower() else "mp4",
                })

    for btn in soup.select("button[data-src], a[data-src]"):
        href = btn.get("data-src", "")
        if href:
            quality = _extract_quality(btn.text)
            sources.append({
                "url": href,
                "quality": quality,
                "provider": "HDHub4U",
                "format": "mp4",
            })

    return sources


def _extract_quality(text: str) -> str:
    m = re.search(r"(1080p|720p|480p|4K|2160p)", text, re.IGNORECASE)
    return m.group(1) if m else "HD"
