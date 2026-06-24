"""
Movies4u provider — CF Workers proxy + GoFile/GDFlix extractors.
Hindi/Bollywood/South Indian content.
"""
import re
from bs4 import BeautifulSoup
from client import cf_get, http_get

CF_PROXY = "https://wild-surf-4a0d.phisher1.workers.dev"
MOVIES4U_DOMAINS = [
    "https://new2.movies4u.style",
    "https://movies4u.day",
    "https://movies4u.zip",
]

HEADERS = {
    "Referer": "https://new2.movies4u.style/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
}


def _fetch_via_proxy(url: str) -> str | None:
    proxied = f"{CF_PROXY}/{url}"
    r = cf_get(proxied, headers=HEADERS, timeout=15)
    if r and len(r) > 1000:
        return r
    return None


def _fetch_direct(url: str) -> str | None:
    r = cf_get(url, headers=HEADERS, timeout=15)
    if r and len(r) > 1000:
        return r
    return None


def _search(title: str) -> str | None:
    for domain in MOVIES4U_DOMAINS:
        url = f"{domain}/?s={title}"
        html = _fetch_via_proxy(url)
        if not html:
            html = _fetch_direct(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True).lower()
            if title.split()[0].lower() in text and href and domain.split("//")[1] in href:
                return href
    return None


def _resolve_gofile(file_id: str) -> str | None:
    acc_r = http_get("https://api.gofile.io/accounts", timeout=10)
    if not acc_r:
        return None
    acc = acc_r.json()
    if acc.get("status") != "ok":
        return None
    token = acc["data"]["token"]

    content_r = http_get(
        f"https://api.gofile.io/contents/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if not content_r:
        return None
    data = content_r.json()
    if data.get("status") != "ok":
        return None

    items = data.get("data", {}).get("contents", [])
    for item in items:
        link = item.get("link", "")
        if link:
            return link
    return None


def _extract_links(html: str) -> list[dict]:
    sources = []
    soup = BeautifulSoup(html, "lxml")

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if not href:
            continue

        quality = _extract_quality(text)

        if "gofile.io" in href:
            m = re.search(r"/d/([a-zA-Z0-9]+)", href)
            if m:
                resolved = _resolve_gofile(m.group(1))
                if resolved:
                    sources.append({"url": resolved, "quality": quality, "provider": "Movies4u", "format": "mkv"})
            else:
                sources.append({"url": href, "quality": quality, "provider": "Movies4u", "format": "mkv"})
        elif any(x in href for x in ["filepress", "gdflix", "pixeldrain", "hubcloud"]):
            sources.append({"url": href, "quality": quality, "provider": "Movies4u", "format": "mkv"})
        elif any(x in href for x in ["streamtape", "embedstream"]):
            sources.append({"url": href, "quality": quality, "provider": "Movies4u", "format": "mp4"})

    for btn in soup.select("button[data-src], a[data-src], [data-url]"):
        href = btn.get("data-src") or btn.get("data-url", "")
        if href:
            quality = _extract_quality(btn.get_text(strip=True))
            sources.append({"url": href, "quality": quality, "provider": "Movies4u", "format": "mp4"})

    return sources


def movies4u(title: str, tmdb_id: str = "") -> list[dict]:
    post_url = _search(title)
    if not post_url:
        return []

    html = _fetch_via_proxy(post_url) or _fetch_direct(post_url)
    if not html:
        return []

    return _extract_links(html)


def _extract_quality(text: str) -> str:
    m = re.search(r"(1080p|720p|480p|4K|2160p)", text, re.IGNORECASE)
    return m.group(1) if m else "HD"
