import re
import json
import os
from urllib.parse import urlparse, urljoin, unquote
from html import unescape as html_unescape
from curl_cffi import requests as cffi_requests
from client import cf_get

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "domain_config.json")

def _load_config():
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

CONFIG = _load_config()


def is_direct_streamable(url: str) -> bool:
    SKIP = [".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".png", ".jpg", ".gif", ".svg", ".ico", ".webp", ".avif"]
    url_lower = url.lower()
    if any(url_lower.endswith(ext) or ext + "?" in url_lower for ext in SKIP):
        return False
    if any(skip in url_lower for skip in ["fonts.googleapis", "cdnjs.cloudflare", "cdn.tailwindcss", "static.cloudflareinsights", "iconfinder", "bootstrap", "fontawesome", "arc.io"]):
        return False
    if "blogger.googleusercontent.com" in url_lower:
        return False
    host = (urlparse(url).hostname or "").lower()
    hosts = CONFIG.get("file_hosts", {}).get("direct_streamable", [])
    for h in hosts:
        h_clean = h.lstrip("*.")
        if h.startswith("*."):
            if host == h_clean or host.endswith("." + h_clean):
                return True
        elif h in host:
            return True
    if re.search(r'\.(mkv|mp4|m3u8|mpd)(?:\?|$)', url, re.IGNORECASE):
        return True
    return False


def _fetch_cffi(url: str, timeout: int = 10) -> tuple[str, str]:
    try:
        r = cffi_requests.get(url, impersonate="chrome", timeout=timeout, allow_redirects=True)
        return r.url, r.text
    except Exception:
        return url, ""


def _fetch_cf(url: str, timeout: int = 10) -> str:
    return cf_get(url, headers={"Referer": url, "User-Agent": _UA}, timeout=timeout) or ""


def _extract_download_links(html: str) -> list[str]:
    patterns = [
        r'href="(https?://[^"]*(?:r2\.dev|r2\.cloudflarestorage)[^"]*)"',
        r'"(https?://[^"]*(?:r2\.dev|r2\.cloudflarestorage)[^"]*)"',
        r'href="(https?://[^"]*pixeldrain[^"]*)"',
        r'"(https?://[^"]*pixeldrain[^"]*)"',
        r'href="(https?://[^"]*drive\.google\.com[^"]*)"',
        r'"(https?://[^"]*drive\.google\.com[^"]*)"',
        r'href="(https?://[^"]*googleusercontent[^"]*)"',
        r'"(https?://[^"]*googleusercontent[^"]*)"',
    ]
    SKIP_PATTERNS = [
        ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
        "fonts.googleapis", "cdnjs.cloudflare", "cdn.tailwindcss",
        "static.cloudflareinsights", "iconfinder.com", "bootstrap",
        "fontawesome", "arc.io", "aclib", "googletagmanager",
        "facebook.net", "twitter.com", "analytics", "widget",
        "blogger.googleusercontent.com",
    ]
    links = []
    seen = set()
    for p in patterns:
        for m in re.findall(p, html):
            m = html_unescape(m)
            if m in seen:
                continue
            if any(skip in m.lower() for skip in SKIP_PATTERNS):
                continue
            seen.add(m)
            links.append(m)
    return links


def resolve_gdflix_auto(url: str, quality: str = "HD", referer: str = "") -> list[dict]:
    results = []
    seen = set()

    rewrite = CONFIG.get("gdflix", {}).get("rewrite_map", {})
    parsed = urlparse(url)
    if parsed.hostname in rewrite:
        url = url.replace(parsed.hostname, rewrite[parsed.hostname])

    def _add(u, q=None):
        u = html_unescape(u)
        if u and u not in seen and is_direct_streamable(u):
            seen.add(u)
            fmt = "mkv" if ".mkv" in u else "mp4"
            results.append({"url": u, "quality": q or quality, "provider": "GDFlix", "format": fmt})

    html = _fetch_cf(url, timeout=15)
    if not html:
        return results

    for link in _extract_download_links(html):
        _add(link)

    key_match = re.search(r'"key"\s*[,:]\s*"([^"]+)"', html)
    if key_match:
        key = key_match.group(1)
        try:
            r = cffi_requests.post(
                url,
                data={"action": "direct", "key": key, "action_token": ""},
                impersonate="chrome",
                timeout=12,
                headers={"x-token": urlparse(url).netloc, "Referer": url}
            )
            if r.status_code == 200:
                try:
                    data = r.json()
                    direct = data.get("url") or data.get("visit_url")
                    if direct:
                        _add(direct)
                except Exception:
                    pass
        except Exception:
            pass

    drivebot_links = re.findall(r'href="(https?://[^"]*drivebot[^"]*)"', html)
    for dl in drivebot_links:
        final_url, body = _fetch_cffi(dl, timeout=10)
        if body:
            for link in _extract_download_links(body):
                _add(link)

    instant_links = re.findall(r'href="(https?://[^"]*instant[^"]*)"', html)
    for il in instant_links:
        final_url, body = _fetch_cffi(il, timeout=10)
        if final_url != il:
            _add(final_url)
        if body:
            for link in _extract_download_links(body):
                _add(link)

    multiup_links = re.findall(r'href="(https?://[^"]*multiup[^"]*)"', html)
    for ml in multiup_links:
        body = _fetch_cf(ml, timeout=10)
        if body:
            for link in _extract_download_links(body):
                _add(link)

    validate_links = re.findall(r'href="(https?://[^"]*validate[^"]*)"', html)
    for vl in validate_links:
        body = _fetch_cf(vl, timeout=10)
        if body:
            for link in _extract_download_links(body):
                _add(link)

    return results


def resolve_hubcloud_auto(url: str, quality: str = "HD", referer: str = "") -> list[dict]:
    results = []
    seen = set()

    def _add(u):
        u = html_unescape(u)
        if u and u not in seen and is_direct_streamable(u):
            seen.add(u)
            fmt = "mkv" if ".mkv" in u else "mp4"
            results.append({"url": u, "quality": quality, "provider": "HubCloud", "format": fmt})

    final_url, html = _fetch_cffi(url, timeout=12)
    if not html:
        return results

    for link in _extract_download_links(html):
        _add(link)

    gamerxyt_links = re.findall(r'href="(https?://[^"]*gamerxyt[^"]*)"', html)
    for gx_url in gamerxyt_links:
        gx_final, gx_html = _fetch_cffi(gx_url, timeout=15)
        if gx_html:
            for link in _extract_download_links(gx_html):
                _add(link)
            for a_link in re.findall(r'href="(https?://[^"]+)"', gx_html):
                if any(x in a_link for x in ["cdn.fsl-buckets", "gpdl.hubcloud", "dolic45578", "workers.dev"]):
                    _add(a_link)

    drivebot_links = re.findall(r'href="(https?://[^"]*drivebot[^"]*)"', html)
    for dl in drivebot_links:
        final_url, body = _fetch_cffi(dl, timeout=10)
        if body:
            for link in _extract_download_links(body):
                _add(link)

    if not results:
        for pattern in [r'"(https?://[^"]*\.(?:mkv|mp4|m3u8|mpd)[^"]*)"']:
            for m in re.findall(pattern, html):
                _add(m)

    return results


def resolve_protector_auto(url: str, quality: str = "HD") -> list[dict]:
    host = (urlparse(url).hostname or "").lower()
    final_url, html = _fetch_cffi(url, timeout=12)

    if is_direct_streamable(final_url) and final_url != url:
        fmt = "mkv" if ".mkv" in final_url else "mp4"
        return [{"url": final_url, "quality": quality, "provider": "LinkProtector", "format": fmt}]

    results = []
    seen = set()

    for link in _extract_download_links(html):
        if link not in seen:
            seen.add(link)
            fmt = "mkv" if ".mkv" in link else "mp4"
            results.append({"url": link, "quality": quality, "provider": "LinkProtector", "format": fmt})

    if "gdflix" in html:
        gdflix_links = re.findall(r'href="(https?://[^"]*gdflix[^"]*)"', html)
        for gl in gdflix_links:
            g_resolved = resolve_gdflix_auto(gl, quality=quality, referer=url)
            for g in g_resolved:
                if g["url"] not in seen:
                    seen.add(g["url"])
                    results.append(g)

    if "hubcloud" in html:
        hubcloud_links = re.findall(r'href="(https?://[^"]*hubcloud[^"]*)"', html)
        for hl in hubcloud_links:
            h_resolved = resolve_hubcloud_auto(hl, quality=quality)
            for h in h_resolved:
                if h["url"] not in seen:
                    seen.add(h["url"])
                    results.append(h)

    if "fastdlserver" in html:
        fastdl_links = re.findall(r'href="(https?://[^"]*fastdlserver[^"]*)"', html)
        for fl in fastdl_links:
            final_fl, fl_html = _fetch_cffi(fl, timeout=10)
            if "gdflix" in final_fl:
                g_resolved = resolve_gdflix_auto(final_fl, quality=quality, referer=fl)
                for g in g_resolved:
                    if g["url"] not in seen:
                        seen.add(g["url"])
                        results.append(g)
            if fl_html:
                for link in _extract_download_links(fl_html):
                    if link not in seen:
                        seen.add(link)
                        fmt = "mkv" if ".mkv" in link else "mp4"
                        results.append({"url": link, "quality": quality, "provider": "LinkProtector", "format": fmt})

    if "direct-dl.lol" in html:
        direct_dl_links = re.findall(r'href="(https?://[^"]*direct-dl\.lol[^"]*)"', html)
        for dl in direct_dl_links:
            d_resolved = resolve_any(dl, quality=quality, referer=url)
            for d in d_resolved:
                if d["url"] not in seen:
                    seen.add(d["url"])
                    results.append(d)

    return results


def resolve_any(url: str, quality: str = "HD", referer: str = "") -> list[dict]:
    if is_direct_streamable(url):
        fmt = "mkv" if ".mkv" in url else "mp4"
        return [{"url": url, "quality": quality, "provider": "Direct", "format": fmt}]

    host = (urlparse(url).hostname or "").lower()

    if "gdflix" in host:
        return resolve_gdflix_auto(url, quality=quality, referer=referer)

    if "hubcloud" in host:
        return resolve_hubcloud_auto(url, quality=quality, referer=referer)

    if "drivebot" in host:
        final_url, html = _fetch_cffi(url, timeout=12)
        if html:
            links = _extract_download_links(html)
            results = []
            for link in links:
                fmt = "mkv" if ".mkv" in link else "mp4"
                results.append({"url": link, "quality": quality, "provider": "DriveBot", "format": fmt})
            return results

    if "fastdlserver" in host:
        final_url, html = _fetch_cffi(url, timeout=12)
        if "gdflix" in final_url:
            return resolve_gdflix_auto(final_url, quality=quality, referer=url)
        if html:
            links = _extract_download_links(html)
            results = []
            for link in links:
                fmt = "mkv" if ".mkv" in link else "mp4"
                results.append({"url": link, "quality": quality, "provider": "FastDL", "format": fmt})
            return results

    if "linksmod" in host:
        final_url, html = _fetch_cffi(url, timeout=10)
        if final_url != url and is_direct_streamable(final_url):
            fmt = "mkv" if ".mkv" in final_url else "mp4"
            return [{"url": final_url, "quality": quality, "provider": "LinksMod", "format": fmt}]
        if html:
            if "gdflix" in html:
                gdflix_links = re.findall(r'href="(https?://[^"]*gdflix[^"]*)"', html)
                for gl in gdflix_links:
                    g_resolved = resolve_gdflix_auto(gl, quality=quality, referer=url)
                    if g_resolved:
                        return g_resolved
            if "hubcloud" in html:
                hubcloud_links = re.findall(r'href="(https?://[^"]*hubcloud[^"]*)"', html)
                for hl in hubcloud_links:
                    h_resolved = resolve_hubcloud_auto(hl, quality=quality, referer=url)
                    if h_resolved:
                        return h_resolved
            if "fastdlserver" in html:
                fastdl_links = re.findall(r'href="(https?://[^"]*fastdlserver[^"]*)"', html)
                for fl in fastdl_links:
                    f_resolved = resolve_any(fl, quality=quality, referer=url)
                    if f_resolved:
                        return f_resolved
            links = _extract_download_links(html)
            if links:
                results = []
                for link in links:
                    fmt = "mkv" if ".mkv" in link else "mp4"
                    results.append({"url": link, "quality": quality, "provider": "LinksMod", "format": fmt})
                return results

    if "hubdrive" in host:
        final_url, html = _fetch_cffi(url, timeout=10)
        if "hubcloud" in html:
            hubcloud_links = re.findall(r'href="(https?://[^"]*hubcloud[^"]*)"', html)
            for hl in hubcloud_links:
                h_resolved = resolve_hubcloud_auto(hl, quality=quality, referer=url)
                if h_resolved:
                    return h_resolved
        if "gdflix" in html:
            gdflix_links = re.findall(r'href="(https?://[^"]*gdflix[^"]*)"', html)
            for gl in gdflix_links:
                g_resolved = resolve_gdflix_auto(gl, quality=quality, referer=url)
                if g_resolved:
                    return g_resolved
        if html:
            links = _extract_download_links(html)
            if links:
                results = []
                for link in links:
                    fmt = "mkv" if ".mkv" in link else "mp4"
                    results.append({"url": link, "quality": quality, "provider": "HubDrive", "format": fmt})
                return results

    if "direct-dl.lol" in host:
        final_url, html = _fetch_cffi(url, timeout=10)
        video_links = re.findall(r'"(https?://[^"]*googleusercontent[^"]*)"', html or "")
        if not video_links:
            video_links = re.findall(r'"(https?://[^"]*\.(?:mp4|mkv|m3u8|mpd)[^"]*)"', html or "")
        if final_url != url and ("googleusercontent" in final_url or ".mp4" in final_url or ".mkv" in final_url):
            fmt = "mkv" if ".mkv" in final_url else "mp4"
            return [{"url": final_url, "quality": quality, "provider": "DirectDL", "format": fmt}]
        results = []
        for link in video_links:
            fmt = "mkv" if ".mkv" in link else "mp4"
            results.append({"url": link, "quality": quality, "provider": "DirectDL", "format": fmt})
        return results

    if "gdxshare" in host:
        final_url, html = _fetch_cffi(url, timeout=10)
        if html:
            links = _extract_download_links(html)
            if links:
                results = []
                for link in links:
                    fmt = "mkv" if ".mkv" in link else "mp4"
                    results.append({"url": link, "quality": quality, "provider": "GdxShare", "format": fmt})
                return results

    return resolve_protector_auto(url, quality=quality)
