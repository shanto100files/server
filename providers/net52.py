import json
import time
from client import cf_get

NET52_BASE = "https://net52.cc"
_NET52_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Referer": NET52_BASE + "/home",
    "X-Requested-With": "XMLHttpRequest",
}

def net52(title: str, tmdb_id: str = "") -> list[dict]:
    sources = []
    try:
        tm = int(time.time())
        search_url = "{}/search.php?s={}&t={}".format(NET52_BASE, title, tm)
        r = cf_get(search_url, headers=_NET52_HEADERS, timeout=8)
        if not r:
            return sources

        data = json.loads(r)
        results = data.get("searchResult", [])
        if not results:
            return sources

        movie_id = results[0].get("id", "")
        if not movie_id:
            return sources

        playlist_url = "{}/playlist.php?id={}&t={}&tm={}".format(
            NET52_BASE, movie_id, title, int(time.time())
        )
        r2 = cf_get(playlist_url, headers=_NET52_HEADERS, timeout=8)
        if not r2:
            return sources

        playlist = json.loads(r2)
        for item in playlist:
            for s in item.get("sources", []):
                file_path = s.get("file", "")
                if not file_path:
                    continue
                url = NET52_BASE + file_path if file_path.startswith("/") else file_path
                label = s.get("label", "HD")
                quality = "1080p" if "Full" in label else "720p" if "Mid" in label else "480p"
                sources.append({
                    "url": url,
                    "quality": quality,
                    "provider": "CNCVerse",
                    "format": "mp4",
                })

    except Exception:
        pass
    return sources
