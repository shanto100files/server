import time
import uuid
from client import http_get, http_post

NETMIRROR_BASE = "https://net52.cc"
IMG_CDN = "https://imgcdn.kim"

PLATFORMS = {
    "netflix": {"ott": "nf", "prefix": "", "search_path": "/mobile/search.php", "post_path": "/mobile/post.php", "playlist_path": "/mobile/playlist.php"},
    "prime": {"ott": "pv", "prefix": "/pv", "search_path": "/pv/search.php", "post_path": "/pv/post.php", "playlist_path": "/pv/playlist.php"},
    "hotstar": {"ott": "hs", "prefix": "/mobile/hs", "search_path": "/mobile/hs/search.php", "post_path": "/mobile/hs/post.php", "playlist_path": "/mobile/hs/playlist.php"},
}

MOBILE_UA = "Mozilla/5.0 (Linux; Android 13; Pixel 5 Build/TQ3A.230901.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/144.0.7559.132 Safari/537.36 /OS.Gatu v3.0"
TV_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0 /OS.GatuNewTV v1.0"

_token_cache = {"value": None, "time": 0}
TOKEN_TTL = 54_000_000

def _get_token() -> str:
    now = time.time() * 1000
    if _token_cache["value"] and (now - _token_cache["time"]) < TOKEN_TTL:
        return _token_cache["value"]

    random_uuid = str(uuid.uuid4())
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/147.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": NETMIRROR_BASE,
        "Referer": f"{NETMIRROR_BASE}/verify2",
    }
    body = f"g-recaptcha-response={random_uuid}"

    try:
        r = http_post(f"{NETMIRROR_BASE}/verify.php", content=body, headers=headers, timeout=10)
        for header_name, header_val in r.headers.items():
            if header_name.lower() == "set-cookie":
                import re
                m = re.search(r"t_hash_t=([^;]+)", header_val)
                if m:
                    _token_cache["value"] = m.group(1)
                    _token_cache["time"] = now
                    return m.group(1)
    except:
        pass
    return ""

def _get_cookies(ott: str) -> str:
    token = _get_token()
    return f"t_hash_t={token}; ott={ott}; hd=on"

def _title_match(query: str, result_title: str) -> bool:
    q = query.lower().strip()
    t = result_title.lower().strip()
    if q == t:
        return True
    if q in t or t in q:
        return True
    qw = set(q.split())
    tw = set(t.split())
    overlap = qw & tw
    if len(overlap) >= max(1, min(len(qw), len(tw)) - 1):
        return True
    return False

_catalog_cache: dict[str, list[dict]] = {}
_CATALOG_TTL = 1800

def _search(query: str, platform: str = "netflix") -> list[dict]:
    cfg = PLATFORMS.get(platform, PLATFORMS["netflix"])
    cache_key = platform
    now = time.time()

    if cache_key in _catalog_cache and (now - _catalog_cache[cache_key][1]) < _CATALOG_TTL:
        all_items = _catalog_cache[cache_key][0]
    else:
        ts = int(now)
        url = f"{NETMIRROR_BASE}{cfg['search_path']}?s=&t={ts}"
        headers = {
            "User-Agent": MOBILE_UA,
            "Cookie": _get_cookies(cfg["ott"]),
            "X-Requested-With": "XMLHttpRequest",
            "Referer": NETMIRROR_BASE,
        }
        all_items = []
        try:
            r = http_get(url, headers=headers, timeout=10)
            if r:
                data = r.json()
                all_items = data.get("searchResult", [])
        except:
            pass
        _catalog_cache[cache_key] = (all_items, now)

    return [item for item in all_items if _title_match(query, item.get("title", item.get("t", "")))]

def _get_post(post_id: str, platform: str = "netflix") -> dict | None:
    cfg = PLATFORMS.get(platform, PLATFORMS["netflix"])
    ts = int(time.time())
    url = f"{NETMIRROR_BASE}{cfg['post_path']}?id={post_id}&t={ts}"
    headers = {
        "User-Agent": TV_UA,
        "Cookie": _get_cookies(cfg["ott"]),
        "X-Requested-With": "XMLHttpRequest",
        "Referer": NETMIRROR_BASE,
    }
    try:
        r = http_get(url, headers=headers, timeout=10)
        if r:
            return r.json()
    except:
        pass
    return None

def _get_playlist(episode_id: str, title: str, platform: str = "netflix") -> list[dict]:
    cfg = PLATFORMS.get(platform, PLATFORMS["netflix"])
    ts = int(time.time())
    url = f"{NETMIRROR_BASE}{cfg['playlist_path']}?id={episode_id}&t={title}&tm={ts}"
    headers = {
        "User-Agent": TV_UA,
        "Cookie": _get_cookies(cfg["ott"]),
        "X-Requested-With": "XMLHttpRequest",
        "Referer": NETMIRROR_BASE,
    }
    try:
        r = http_get(url, headers=headers, timeout=10)
        if r:
            data = r.json()
            if isinstance(data, list):
                return data
            return data.get("videoLinks", [])
    except:
        pass
    return []

def _extract_streams(post_data: dict, post_id: str = "", platform: str = "netflix") -> list[dict]:
    streams = []
    episodes = [e for e in post_data.get("episodes", []) if e]
    if not episodes:
        title = post_data.get("title", "Video")
        if post_id:
            playlist = _get_playlist(str(post_id), title, platform)
            for v in playlist:
                sources_list = v.get("sources", [])
                for src in sources_list:
                    file_url = src.get("file", "")
                    quality = src.get("label", "HD")
                    if file_url:
                        if not file_url.startswith("http"):
                            file_url = f"https:{file_url}" if file_url.startswith("//") else f"{NETMIRROR_BASE}{file_url}"
                        streams.append({
                            "url": file_url,
                            "quality": quality,
                            "provider": f"NetMirror-{platform.title()}",
                            "format": "hls",
                        })
    else:
        for ep in episodes:
            if not ep:
                continue
            eid = ep.get("id")
            title = ep.get("title", ep.get("t", "Episode"))
            if eid:
                playlist = _get_playlist(str(eid), title, platform)
                for v in playlist:
                    sources_list = v.get("sources", [])
                    for src in sources_list:
                        file_url = src.get("file", "")
                        quality = src.get("label", "HD")
                        if file_url:
                            if not file_url.startswith("http"):
                                file_url = f"https:{file_url}" if file_url.startswith("//") else f"{NETMIRROR_BASE}{file_url}"
                            streams.append({
                                "url": file_url,
                                "quality": quality,
                                "provider": f"NetMirror-{platform.title()}",
                                "format": "hls",
                            })
    return streams

def netmirror_search(title: str, tmdb_id: str = "", platforms: list[str] = None) -> list[dict]:
    return []
    sources = []
    if platforms is None:
        platforms = ["netflix", "prime", "hotstar"]

    for plat in platforms:
        results = _search(title, plat)
        if not results:
            continue

        best = results[0]
        post_id = best.get("id")
        if not post_id:
            continue

        post_data = _get_post(str(post_id), plat)
        if not post_data:
            continue

        streams = _extract_streams(post_data, str(post_id), plat)
        sources.extend(streams)

    return sources

def netmirror_direct(post_id: str, platform: str = "netflix") -> list[dict]:
    post_data = _get_post(post_id, platform)
    if not post_data:
        return []
    return _extract_streams(post_data, post_id, platform)
