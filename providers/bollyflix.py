import re
from bs4 import BeautifulSoup
from client import cf_get
from urllib.parse import urlparse
from providers.auto_resolver import resolve_any, is_direct_streamable, content_matches, title_matches_search, score_content

BASE = "https://bollyflix.med"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"


def _search(title: str) -> list[dict]:
    url = f"{BASE}/?s={title}"
    html = cf_get(url, headers={"Referer": BASE, "User-Agent": UA}, timeout=15)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []
    for article in soup.select("article"):
        a = article.select_one("a[href]")
        img = article.select_one("img")
        title_el = article.select_one("h2.title a, h2.entry-title a, .front-view-title a")
        if not a or not title_el:
            continue
        href = a.get("href", "")
        name = title_el.get_text(strip=True)
        poster = ""
        if img:
            poster = img.get("src", "") or img.get("data-src", "")
        if href and name:
            results.append({"url": href, "title": name, "poster": poster})
    return results


def _extract_links(html: str, post_url: str = "") -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    sources = []
    seen = set()

    all_download_links = []

    for a in soup.select("a.maxbutton, a.button-download-links"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if not href or href in seen:
            continue
        seen.add(href)
        quality = "HD"
        q_match = re.search(r"(2160p|1080p|720p|480p)", text + " " + href)
        if q_match:
            quality = q_match.group(1)
        all_download_links.append((href, quality))

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if not href or href in seen:
            continue
        host = (urlparse(href).hostname or "").lower()
        is_dl = any(x in href for x in ["linksmod", "fastdlserver", "fxlinks", "techzed", "hubcloud", "hubdrive", "gdflix", "neodrive", "drive"]) or \
                any(x in text.lower() for x in ["download", "1080p", "720p", "480p", "google drive"])
        if is_dl:
            seen.add(href)
            quality = "HD"
            q_match = re.search(r"(2160p|1080p|720p|480p)", text + " " + href)
            if q_match:
                quality = q_match.group(1)
            all_download_links.append((href, quality))

    for href, quality in all_download_links[:8]:
        if len(sources) >= 8:
            break
        resolved = resolve_any(href, quality=quality, referer=post_url)
        for r in resolved[:2]:
            url = r.get("url", "")
            if url in seen:
                continue
            if not is_direct_streamable(url):
                continue
            seen.add(url)
            sources.append(r)

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

    html = cf_get(best["url"], headers={"Referer": BASE, "User-Agent": UA}, timeout=15)
    if not html:
        return []

    sources = _extract_links(html, post_url=best["url"])
    scored = []
    for s in sources:
        sc = score_content(s.get("url", ""), title, year, media_type)
        if sc >= 25:
            s["relevance_score"] = sc
            scored.append(s)
    scored.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return scored[:8]
