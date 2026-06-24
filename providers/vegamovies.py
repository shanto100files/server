import re
from bs4 import BeautifulSoup
from client import cf_get

VEGAMOVIES_DOMAINS = ["https://vegamovie.sl", "https://vegamovies.tel", "https://vegamovies.com"]

def _fetch(url: str, headers: dict = None) -> str | None:
    return cf_get(url, headers=headers, timeout=10)

def _extract_quality(text: str) -> str:
    m = re.search(r"(1080p|720p|480p|4K|2160p)", text, re.IGNORECASE)
    return m.group(1) if m else "HD"

def _extract_size(text: str) -> str:
    m = re.search(r"([\d.]+\s*(?:GB|MB|KB))", text, re.IGNORECASE)
    return m.group(1) if m else ""

def vegamovies(title: str, tmdb_id: str = "") -> list[dict]:
    sources = []

    for domain in VEGAMOVIES_DOMAINS:
        html = _fetch(f"{domain}/?s={title}", headers={"Referer": domain})
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")
        posts = soup.select("article a, .post-title a, h2 a, h3 a")
        if not posts:
            continue

        post_url = None
        for p in posts:
            href = p.get("href", "")
            text = p.get_text(strip=True).lower()
            if href and title.split()[0].lower() in text and domain in href:
                post_url = href
                break
        if not post_url:
            post_url = posts[0].get("href", "")
        if not post_url:
            continue

        post_html = _fetch(post_url, headers={"Referer": domain})
        if not post_html:
            continue

        post_soup = BeautifulSoup(post_html, "lxml")

        for a in post_soup.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if not href:
                continue

            if any(x in href for x in ["nexdrive", "fast-dl", "savelinks", "gdflix", "hubdrive", "hubcloud", "pixeldrain", "filepress"]):
                quality = _extract_quality(text)
                size = _extract_size(text)
                fmt = "mkv" if "mkv" in text.lower() else "mp4"
                source = {
                    "url": href,
                    "quality": quality,
                    "provider": "VegaMovies",
                    "format": fmt,
                }
                if size:
                    source["fileSize"] = size
                sources.append(source)

        for btn in post_soup.select("button[data-src], a[data-src]"):
            href = btn.get("data-src", "")
            if href:
                quality = _extract_quality(btn.text)
                sources.append({
                    "url": href,
                    "quality": quality,
                    "provider": "VegaMovies",
                    "format": "mp4",
                })

        if sources:
            break

    return sources
