"""
FlixSearch provider — searches multiple file hosts for streaming links.
Uses GDFlix, FSLeech, and other open resolvers.
"""
import re
from urllib.parse import quote as urlquote
from client import cf_get, http_get
from providers.auto_resolver import resolve_any, is_direct_streamable


def _search_fslim(title: str) -> list[str]:
    urls = []
    q = urlquote(title)
    
    search_urls = [
        f"https://cinevexus.net/?s={q}",
        f"https://vegamovies.dev/?s={q}",
    ]
    
    for site_url in search_urls:
        html = cf_get(site_url, timeout=10)
        if not html:
            continue
        
        links = re.findall(r'href="(https?://[^"]*cinevexus\.net/[^"]+)"', html)
        if not links:
            links = re.findall(r'href="(https?://[^"]*vegamovies\.dev/[^"]+)"', html)
        
        for link in links[:3]:
            if link not in urls:
                urls.append(link)
    
    return urls


def _extract_from_fslim(post_url: str) -> list[str]:
    html = cf_get(post_url, timeout=10)
    if not html:
        return []
    
    link_patterns = [
        r'href="(https?://[^"]*(?:gdflix|hubcloud|drivebot|fastdl|pixeldrain|google\.com/drive|mega\.nz|r2\.dev)[^"]*)"',
        r'href="(https?://[^"]*(?:filepress|streamtape|doodstream|mixdrop|upstream)[^"]*)"',
        r'"(https?://[^"]*\.(?:m3u8|mp4|mkv)(?:\?[^"]*)?)"',
    ]
    
    results = []
    for pattern in link_patterns:
        matches = re.findall(pattern, html)
        results.extend(matches)
    
    return list(set(results))[:8]


def _search_gdlink(title: str) -> list[str]:
    q = urlquote(title)
    urls = []
    
    search_sites = [
        f"https://google.com/search?q={q}+gdflix+download",
    ]
    
    for url in search_sites:
        html = http_get(url, timeout=8)
        if not html:
            continue
        
        dl_links = re.findall(r'href="(https?://[^"]*(?:gdflix|drive|pixeldrain|r2\.dev)[^"]*)"', html.text if hasattr(html, 'text') else "")
        urls.extend(dl_links[:6])
    
    return list(set(urls))[:6]


def flixsearch(title: str, tmdb_id: str = "") -> list[dict]:
    sources = []
    seen = set()
    
    all_links = []
    
    try:
        fslim_links = _search_fslim(title)
        for link in fslim_links:
            extracted = _extract_from_fslim(link)
            all_links.extend(extracted)
    except Exception:
        pass
    
    try:
        gdlink_links = _search_gdlink(title)
        all_links.extend(gdlink_links)
    except Exception:
        pass
    
    for url in all_links:
        clean = url.split("?")[0].rstrip("/")
        if clean in seen:
            continue
        seen.add(clean)
        
        resolved = resolve_any(url)
        if resolved:
            for r in resolved:
                r_url = r.get("url", "")
                if is_direct_streamable(r_url):
                    r_clean = r_url.split("?")[0]
                    if r_clean not in seen:
                        seen.add(r_clean)
                        sources.append({
                            "url": r_url,
                            "quality": r.get("quality", "HD"),
                            "provider": "FlixSearch",
                            "format": r.get("format", "mp4"),
                        })
        elif is_direct_streamable(url):
            fmt = "mp4"
            if ".m3u8" in url:
                fmt = "hls"
            elif ".mkv" in url:
                fmt = "mkv"
            elif ".mpd" in url:
                fmt = "dash"
            sources.append({
                "url": url,
                "quality": "HD",
                "provider": "FlixSearch",
                "format": fmt,
            })
    
    return sources[:15]
