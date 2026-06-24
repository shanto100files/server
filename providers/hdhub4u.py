import re
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from client import cf_get
from providers.hubcloud import extract_hubcloud
from providers.gdflix import resolve_gdflix
from providers.hubdrive import resolve_hubdrive

HDHUB4U_SEARCH_API = "https://search.pingora.fyi/collections/post/documents/search"
HDHUB4U_DOMAINS = ["https://new2.hdhub4u.limo", "https://new2.hdhub4u.cl", "https://hdhub4u.lt"]

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def _title_match(query: str, post_title: str) -> bool:
    q = query.lower().strip()
    t = post_title.lower().strip()
    if q == t:
        return True
    if q in t and len(q) >= 3:
        qw = set(q.split())
        tw = set(t.split())
        if len(qw & tw) >= max(1, len(qw) - 1):
            return True
    qw = set(q.split())
    tw = set(t.split())
    overlap = qw & tw
    if len(overlap) >= max(1, min(len(qw), len(tw)) - 1):
        return True
    return False

def _search(title: str) -> str | None:
    params = {
        "q": title,
        "query_by": "post_title,category,stars,director,imdb_id",
        "query_by_weights": "4,2,2,2,4",
        "sort_by": "sort_by_date:desc",
        "limit": "5",
        "page": "1",
    }
    try:
        r = cffi_requests.get(HDHUB4U_SEARCH_API, params=params, impersonate="chrome",
                               headers={"Referer": "https://new2.hdhub4u.limo/", "Origin": "https://new2.hdhub4u.limo"},
                               timeout=15)
        if r.status_code == 200:
            data = r.json()
            hits = data.get("hits", [])
            for hit in hits:
                doc = hit.get("document", {})
                post_title = doc.get("post_title", "")
                if _title_match(title, post_title):
                    permalink = doc.get("permalink", "")
                    if permalink:
                        return permalink
    except:
        pass
    return None


def hdhub4u(title: str, tmdb_id: str = "") -> list[dict]:
    sources = []

    permalink = _search(title)
    if not permalink:
        return sources

    post_url = None
    for domain in HDHUB4U_DOMAINS:
        test_url = f"{domain}{permalink}"
        try:
            r = cffi_requests.get(test_url, impersonate="chrome", timeout=10)
            if r.status_code == 200 and len(r.text) > 1000:
                post_url = test_url
                break
        except:
            continue

    if not post_url:
        return sources

    post_html = cf_get(post_url, timeout=15)
    if not post_html:
        return sources

    soup = BeautifulSoup(post_html, "lxml")

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if not href:
            continue

        quality = _extract_quality(text)

        if any(x in href for x in ["hubcloud", "gdflix"]):
            if "gdflix" in href:
                gdflix_resolved = resolve_gdflix(href, quality=quality, referer=post_url)
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
                resolved = extract_hubcloud(href, quality=quality, referer=post_url)
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
                hub_resolved = resolve_hubdrive(href)
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
