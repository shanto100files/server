import re
from client import cf_get, http_get
from urllib.parse import urlparse, unquote
from html import unescape as html_unescape

_GDFLIX_DOMAINS = [
    "https://new1.gdflix.io",
    "https://gdflix.cc",
    "https://gdflix.online",
]
_GDFLIX_MAP = {
    "new.gdflix.com": "new1.gdflix.io",
    "gdflix.top": "new1.gdflix.io",
    "gdflix.org": "new1.gdflix.io",
    "gdflix.cfd": "new1.gdflix.io",
    "gdflix.dev": "new1.gdflix.io",
}
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

NON_STREAMABLE_HOSTS = [
    "megaup.net", "mega.nz", "mega.co.nz",
    "rapidgator.net", "rapidgator.cc", "rg.to",
    "1fichier.com", "1fichier.fr",
    "gofile.io",
    "katfile.com", "nitroflare.com", "Uploaded.net",
    "turbobit.net", "keep2share.cc", "fileboom.me",
    "mixdrop.co", "doodstream.com", "streamtape.com",
    "drivebot.sbs", "filesgram.xyz",
]

RESOLVABLE_HOSTS = [
    "instant.busycdn.xyz",
    "instant.cdn-worker.com",
]

def _is_streamable(url: str) -> bool:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    for bad in NON_STREAMABLE_HOSTS:
        if bad in host:
            return False
    if "pixeldrain" in host:
        return True
    if any(x in url for x in ["r2.dev", "r2.cloudflarestorage", "drive.google.com"]):
        return True
    if any(x in host for x in ["workers.dev", "pages.dev", "blob.core.windows.net"]):
        return True
    if re.search(r'\.(mkv|mp4|m3u8)(?:\?|$)', url):
        return True
    return False


def _rewrite_domain(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host in _GDFLIX_MAP:
        return url.replace(host, _GDFLIX_MAP[host], 1)
    return url


def _resolve_instant(url: str) -> str:
    from curl_cffi import requests as cffi_requests
    try:
        r = cffi_requests.get(url, impersonate="chrome", timeout=15, allow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"})
        if r.url != url:
            return r.url
        body = r.text
        m = re.search(r'fastcdn-dl\.pages\.dev/\?url=([^"\'<>\s]+)', body)
        if m:
            return m.group(1).replace("&amp;", "&")
        m2 = re.search(r'"(https?://video-downloads\.googleusercontent\.com/[^"]+)"', body)
        if m2:
            return html_unescape(m2.group(1))
        m3 = re.search(r'"(https?://[^"]*googleusercontent\.com/[^"]+)"', body)
        if m3:
            return html_unescape(m3.group(1))
    except Exception:
        pass
    return ""


def resolve_gdflix(url: str, quality: str = "", referer: str = "") -> list[dict]:
    results = []
    try:
        url = _rewrite_domain(url)
        html = cf_get(url, headers={"Referer": referer or url}, timeout=20)
        if not html:
            for alt in _GDFLIX_DOMAINS:
                if alt in url:
                    continue
                alt_url = url.replace(urlparse(url).scheme + "://" + urlparse(url).netloc, alt)
                html = cf_get(alt_url, headers={"Referer": referer or alt_url}, timeout=15)
                if html:
                    url = alt_url
                    break
            if not html:
                return results

        _seen = set()
        def _add(u, q=None, fmt="mp4"):
            if u and u not in _seen and _is_streamable(u):
                _seen.add(u)
                results.append({
                    "url": u,
                    "quality": q or quality or "HD",
                    "provider": "GDFlix",
                    "format": fmt,
                })

        def _add_links(pattern, fmt_override=None):
            for link in re.findall(pattern, html):
                link = html_unescape(link)
                fmt = fmt_override or "mkv"
                _add(link, quality, fmt)

        _add_links(r'href="(https?://[^"]*(?:r2\.dev|r2\.cloudflarestorage)[^"]*)"')
        _add_links(r'href="(https?://[^"]*drive\.google\.com[^"]*)"')

        instant_links = re.findall(r'href="(https?://[^"]*instant[^"]*)"', html)
        for il in instant_links:
            il = html_unescape(il)
            resolved = _resolve_instant(il)
            if resolved:
                _add(resolved, quality, "mkv")
            else:
                _add(il, quality, "mkv")

        pixeldrain_links = re.findall(r'href="(https?://[^"]*pixeldrain[^"]*)"', html)
        for pl in pixeldrain_links:
            pl = html_unescape(pl)
            m = re.search(r'pixeldrain\.dev/u/([a-zA-Z0-9]+)', pl)
            if m:
                api_url = f"https://pixeldrain.dev/api/file/{m.group(1)}"
                _add(api_url, quality, "mkv")
            else:
                _add(pl, quality, "mkv")

        multiup_links = re.findall(r'href="(https?://[^"]*multiup[^"]*)"', html)
        for mulink in multiup_links:
            mulink = html_unescape(mulink)
            _resolve_multiup(mulink, _add, quality)

        key_match = re.search(r'"key"\s*[,:]\s*"([^"]+)"', html)
        if key_match:
            key = key_match.group(1)
            parsed = urlparse(url)

            from curl_cffi import requests as cffi_requests
            r = cffi_requests.post(
                url,
                data={"action": "direct", "key": key, "action_token": ""},
                impersonate="chrome",
                timeout=15,
                headers={"x-token": parsed.netloc, "Referer": url}
            )
            if r.status_code == 200:
                try:
                    data = r.json()
                    direct_url = data.get("url") or data.get("visit_url")
                    if direct_url:
                        _add(direct_url, quality, "mkv")
                except:
                    pass

        validate_links = re.findall(r'href="(https?://validate[^"]*)"', html)
        for vlink in validate_links:
            vlink = html_unescape(vlink)
            _resolve_multiup(vlink, _add, quality)

    except Exception:
        pass

    return results


def _resolve_multiup(url: str, add_fn, quality: str = ""):
    try:
        html = cf_get(url, timeout=15)
        if not html:
            return

        others = re.findall(r'"(https?://[^"]+\.(?:mkv|mp4|m3u8)(?:\?[^"]*)?)"', html)
        for o in others:
            add_fn(html_unescape(o), quality, "mkv")

        r2_links = re.findall(r'"(https?://[^"]*(?:r2\.dev|r2\.cloudflarestorage)[^"]*)"', html)
        for r in r2_links:
            add_fn(html_unescape(r), quality, "mkv")

        gd_links = re.findall(r'"(https?://[^"]*drive\.google\.com[^"]*)"', html)
        for g in gd_links:
            add_fn(html_unescape(g), quality, "mkv")

        pd_links = re.findall(r'"(https?://[^"]*pixeldrain[^"]*)"', html)
        for p in pd_links:
            add_fn(html_unescape(p), quality, "mkv")

    except Exception:
        pass


def extract_key_from_page(html: str) -> str:
    m = re.search(r'"key"\s*[,:]\s*"([^"]+)"', html)
    return m.group(1) if m else ""


def extract_links_from_html(html: str, quality: str = "") -> list[dict]:
    results = []
    seen = set()

    patterns = [
        r'href="(https?://[^"]*(?:r2\.dev|r2\.cloudflarestorage)[^"]*)"',
        r'href="(https?://[^"]*drive\.google\.com[^"]*)"',
        r'href="(https?://[^"]*pixeldrain[^"]*)"',
        r'"(https?://[^"]*(?:r2\.dev|r2\.cloudflarestorage)[^"]*)"',
    ]

    for pat in patterns:
        for link in re.findall(pat, html):
            link = html_unescape(link)
            if link not in seen and _is_streamable(link):
                seen.add(link)
                results.append({
                    "url": link,
                    "quality": quality or "HD",
                    "provider": "GDFlix",
                    "format": "mkv",
                })

    return results
