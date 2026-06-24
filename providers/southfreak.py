import re
from bs4 import BeautifulSoup
from client import cf_get
from curl_cffi import requests as cffi_requests
from providers.auto_resolver import resolve_any, resolve_protector_auto, is_direct_streamable

BASE = "https://southfreak.fyi"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"


def _search(title: str) -> list[dict]:
    url = f"{BASE}/?s={title}"
    html = cf_get(url, headers={"Referer": BASE, "User-Agent": UA}, timeout=15)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []
    seen_urls = set()

    for container in soup.select("figure, .thumb"):
        a = container.select_one("a[href]")
        name_el = container.select_one("figcaption a p, figcaption a")
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

    return results


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
    for href, text in download_links[:5]:
        if len(sources) >= 4:
            break

        q_in_text = re.search(r"(2160p|1080p|720p|480p)", text + " " + href)
        if q_in_text:
            current_quality = q_in_text.group(1)

        if href in seen:
            continue
        seen.add(href)

        resolved = resolve_any(href, quality=current_quality, referer=post_url)
        for r in resolved[:2]:
            if r["url"] not in seen:
                seen.add(r["url"])
                sources.append(r)

    return sources


def southfreak(title: str, tmdb_id: str = "") -> list[dict]:
    results = _search(title)
    if not results:
        return []

    best = None
    title_lower = title.lower().strip()
    for r in results:
        rt = r["title"].lower()
        if title_lower in rt or rt in title_lower:
            best = r
            break
        words = set(title_lower.split())
        rwords = set(rt.split())
        if len(words & rwords) >= max(1, len(words) - 1):
            best = r
            break
    if not best:
        best = results[0]

    html = cf_get(best["url"], headers={"Referer": BASE, "User-Agent": UA}, timeout=15)
    if not html:
        return []

    sources = _extract_links(html, post_url=best["url"])
    return sources
