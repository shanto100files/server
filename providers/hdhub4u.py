import re
import time
import threading
import asyncio
from bs4 import BeautifulSoup
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
    try:
        index_r = await async_cf_get(f"{_PRIMARY}/sitemap.xml", timeout=12)
        if not index_r:
            return []
        soup = BeautifulSoup(index_r, "xml.etree.ElementTree")
        post_sitemaps = [loc.text for loc in soup.select("loc") if "post-sitemap" in loc.text]
        for sm_url in post_sitemaps:
            sm_html = await async_cf_get(sm_url, timeout=12)
            if sm_html:
                sm_soup = BeautifulSoup(sm_html, "xml.etree.ElementTree")
                urls.extend(loc.text for loc in sm_soup.select("loc"))
    except Exception:
        pass

    if urls:
        with _sitemap_lock:
            _sitemap_cache["urls"] = urls
            _sitemap_cache["ts"] = time.time()

    return urls


def _slug_match(query: str, url: str) -> float:
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(
        r"-(1080p|720p|480p|4k|2160p|bluray|web-dl|webrip|dvdrip|hdtv|hdcam|cam|pdvdrip|hdrip|hevc|x264|x265|10bit|full|movie|hindi|english|dual.?audio).*",
        "",
        slug,
        flags=re.I,
    )
    slug_title = re.sub(r"-\d{4}(-|$)", "", slug).replace("-", " ").strip().lower()
    q = query.lower().strip()

    if q == slug_title:
        return 100.0

    qw = set(q.split())
    sw = set(slug_title.split())
    if not qw or not sw:
        return 0.0

    overlap = qw & sw
    precision = len(overlap) / len(qw) if qw else 0
    recall = len(overlap) / len(sw) if sw else 0

    if not overlap:
        return 0.0

    score = (precision * 60 + recall * 40)
    if len(overlap) == len(qw) and len(overlap) == len(sw):
        score = 99.0

    year_match = re.search(r"(\d{4})", slug)
    if year_match:
        score += 5

    return score


async def _search_sitemap(title: str) -> str | None:
    urls = await _load_sitemap()
    if not urls:
        return None

    scored = []
    for url in urls:
        score = _slug_match(title, url)
        if score >= 40:
            scored.append((score, url))
    scored.sort(reverse=True)

    if scored:
        return scored[0][1]
    return None


async def _search_direct(title: str) -> str | None:
    """Fallback: scrape search page when sitemap doesn't have the movie."""
    for domain in HDHUB4U_DOMAINS:
        try:
            from urllib.parse import quote
            html = await async_cf_get(f"{domain}/?s={quote(title)}", timeout=10)
            if not html or len(html) < 500:
                continue
            soup = BeautifulSoup(html, "html.parser")
            qw = set(title.lower().split())
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                text = a.get_text(strip=True).lower()
                if not href or "/?s=" in href or href.rstrip("/") == domain:
                    continue
                if any(x in href for x in ["/page/", "/tag/", "/category/", "search.html"]):
                    continue
                if not href.startswith("http") and not href.startswith("/"):
                    continue
                tw = set(text.split())
                overlap = qw & tw
                if len(overlap) >= max(1, len(qw) - 1):
                    if href.startswith("http"):
                        from urllib.parse import urlparse
                        parsed = urlparse(href)
                        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    return href
        except Exception:
            continue

        # Fallback: try searching via google dork
        try:
            from urllib.parse import quote
            g_url = f"https://www.google.com/search?q=site:{domain.split('//')[1]}+{quote(title)}"
            g_html = await async_cf_get(g_url, timeout=8)
            if g_html:
                import re
                found = re.search(rf'href="(https?://{re.escape(domain.split("//")[1])}/[^"]+)"', g_html)
                if found:
                    from urllib.parse import urlparse
                    parsed = urlparse(found.group(1))
                    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        except Exception:
            pass
    return None


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
