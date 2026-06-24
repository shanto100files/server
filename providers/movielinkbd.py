import re
from bs4 import BeautifulSoup
from client import cf_get
from providers.gdflix import resolve_gdflix

MOVELINKBD_BASE = "https://movielinkbd.com"

def _fetch(url: str, headers: dict = None) -> str | None:
    return cf_get(url, headers=headers, timeout=15)

def movielinkbd(title: str, tmdb_id: str = "") -> list[dict]:
    sources = []

    html = _fetch(f"{MOVELINKBD_BASE}/?s={title}")
    if not html:
        return sources

    soup = BeautifulSoup(html, "lxml")
    posts = soup.select("article a, .post-title a, h2 a, h3 a")
    if not posts:
        return sources

    post_url = posts[0].get("href", "")
    if not post_url:
        return sources

    post_html = _fetch(post_url)
    if not post_html:
        return sources

    post_soup = BeautifulSoup(post_html, "lxml")

    for a in post_soup.select("a[href]"):
        href = a.get("href", "")
        text = a.text.strip()
        if not href:
            continue

        if any(x in href for x in ["/getLink/", "/getWatch/", "filepress", "gdflix", "pixeldrain"]):
            quality = _extract_quality(text)
            fmt = "mkv" if "mkv" in text.lower() else "mp4"
            if "/getWatch/" in href:
                fmt = "m3u8"
            if "gdflix" in href:
                gdflix_resolved = resolve_gdflix(href, quality=quality, referer=post_url)
                if gdflix_resolved:
                    for g in gdflix_resolved:
                        sources.append(g)
                else:
                    sources.append({
                        "url": href,
                        "quality": quality,
                        "provider": "MovieLinkBD",
                        "format": fmt,
                    })
            else:
                sources.append({
                    "url": href,
                    "quality": quality,
                    "provider": "MovieLinkBD",
                    "format": fmt,
                })

    return sources

def _extract_quality(text: str) -> str:
    m = re.search(r"(1080p|720p|480p|4K|2160p)", text, re.IGNORECASE)
    return m.group(1) if m else "HD"
