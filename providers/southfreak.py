import re
from bs4 import BeautifulSoup
from client import async_cf_get
from providers.auto_resolver import title_matches_search

SOUTHFREAK_DOMAINS = ["https://southfreak.fyi", "https://southfreak.me"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"


async def _search(title: str) -> list[dict]:
    for BASE in SOUTHFREAK_DOMAINS:
        url = f"{BASE}/?s={title}"
        html = await async_cf_get(url, headers={"Referer": BASE, "User-Agent": UA}, timeout=10)
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")
        results = []
        seen_urls = set()

        for container in soup.select("figure, .thumb, article"):
            a = container.select_one("a[href]")
            name_el = container.select_one("figcaption a p, figcaption a, h2 a, .entry-title a")
            img = container.select_one("img")
            if not a or not name_el:
                continue
            href = a.get("href", "")
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)
            name = name_el.get_text(strip=True)
            poster = img.get("src", "") if img else ""
            results.append({"url": href, "title": name, "poster": poster})

        if results:
            return results
    return []


def _extract_links(html: str, post_url: str = "") -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    sources = []
    seen = set()

    download_links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if not href:
            continue
        is_dl = any(x in href for x in ["techzed", "gdflix", "hubcloud", "fxlinks", "fastdl", "drive", "r2.dev", "pixeldrain"]) or \
                any(x in text.lower() for x in ["download", "1080p", "720p", "480p", "2160p", "4k"])
        if is_dl:
            download_links.append((href, text))

    current_quality = "HD"
    for href, text in download_links[:2]:
        if len(sources) >= 4:
            break

        if "how-to-download" in href or "southfreak" in href:
            continue

        q_in_text = re.search(r"(2160p|1080p|720p|480p)", text + " " + href)
        if q_in_text:
            current_quality = q_in_text.group(1)

        if href in seen:
            continue
        seen.add(href)

        sources.append({
            "url": href,
            "quality": current_quality,
            "provider": "SouthFreak",
            "format": "mp4",
        })

    return sources


async def southfreak(title: str, tmdb_id: str = "", year: str = "", media_type: str = "") -> list[dict]:
    results = await _search(title)
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

    html = await async_cf_get(best["url"], headers={"Referer": best["url"], "User-Agent": UA}, timeout=10)
    if not html:
        return []

    sources = _extract_links(html, post_url=best["url"])
    return sources[:8]
