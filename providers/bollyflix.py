import re
from bs4 import BeautifulSoup
from client import cf_get
from urllib.parse import urlparse
from providers.auto_resolver import title_matches_search

BOLLYFLIX_DOMAINS = ["https://bollyflix.med", "https://bollyflix.run"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"


def _search(title: str) -> list[dict]:
    for BASE in BOLLYFLIX_DOMAINS:
        url = f"{BASE}/?s={title}"
        html = cf_get(url, headers={"Referer": BASE, "User-Agent": UA}, timeout=10)
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")
        results = []

        for a in soup.select("article a[href], .post a[href], a.post-image"):
            href = a.get("href", "")
            name = a.get("title", "") or a.get_text(strip=True)
            if not href or not name:
                continue
            img = a.select_one("img")
            poster = img.get("src", "") or img.get("data-src", "") if img else ""
            results.append({"url": href, "title": name, "poster": poster})

        if results:
            return results
    return []


def _extract_links(html: str, post_url: str = "") -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    sources = []
    seen = set()

    all_download_links = []

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if not href or href in seen:
            continue
        host = (urlparse(href).hostname or "").lower()
        is_dl = any(x in href for x in ["linksmod", "fastdlserver", "fxlinks", "techzed", "hubcloud", "hubdrive", "gdflix", "neodrive", "gadgetsweb"]) or \
                any(x in href for x in ["drive.google.com", "pixeldrain", "r2.dev", "mega.nz"])
        if is_dl and "bollyflix" not in host and "how-to-download" not in href:
            seen.add(href)
            quality = "HD"
            q_match = re.search(r"(2160p|1080p|720p|480p)", text + " " + href)
            if q_match:
                quality = q_match.group(1)
            all_download_links.append((href, quality))

    for href, quality in all_download_links[:5]:
        if len(sources) >= 5:
            break
        sources.append({
            "url": href,
            "quality": quality,
            "provider": "BollyFlix",
            "format": "mp4",
        })

    return sources


def bollyflix(title: str, tmdb_id: str = "", year: str = "", media_type: str = "") -> list[dict]:
    results = _search(title)
    if not results:
        return []

    best = None
    for r in results:
        if title_matches_search(r["title"], title, query_year=year):
            best = r
            break
    if not best:
        for r in results:
            rt = r["title"].lower()
            tw = set(title.lower().split())
            rw = set(rt.split())
            if len(tw & rw) >= max(1, len(tw) - 1):
                best = r
                break
    if not best:
        return []

    html = cf_get(best["url"], headers={"Referer": best["url"], "User-Agent": UA}, timeout=10)
    if not html:
        return []

    sources = _extract_links(html, post_url=best["url"])
    return sources[:8]
