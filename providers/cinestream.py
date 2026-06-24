import json
from client import http_get, http_post

VIDEASY_BASE = "https://api.videasy.to"
DECRYPT_URL = "https://enc-dec.app/api/dec-videasy"
REFERER = "https://cineby.at"
ORIGIN = "https://cineby.at"

SOURCES = [
    {"name": "Neon", "path": "mb-flix"},
    {"name": "Yoru", "path": "cdn", "movie_only": True},
    {"name": "Cypher", "path": "downloader2"},
    {"name": "Sage", "path": "1movies"},
    {"name": "Breach", "path": "m4uhd"},
    {"name": "Vyse", "path": "hdmovie"},
]

def _resolve_source(source: dict, title: str, media_type: str, year: str = "", tmdb_id: str = "", imdb_id: str = "", season_id: str = "", episode_id: str = "") -> list[dict]:
    streams = []
    try:
        params = {
            "title": title,
            "mediaType": media_type,
        }
        if year:
            params["year"] = year
        if tmdb_id:
            params["tmdbId"] = tmdb_id
        if imdb_id:
            params["imdbId"] = imdb_id
        if season_id:
            params["seasonId"] = season_id
        if episode_id:
            params["episodeId"] = episode_id

        from urllib.parse import urlencode
        full_url = f"{VIDEASY_BASE}/{source['path']}/sources-with-title?{urlencode(params)}"
        headers = {
            "Referer": REFERER,
            "Origin": ORIGIN,
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 5) AppleWebKit/537.36 Chrome/144.0.7559.132 Mobile Safari/537.36",
        }

        r = http_get(full_url, headers=headers, timeout=10)
        if r:
            raw_text = r.text
        else:
            return streams

        if not raw_text or len(raw_text) < 10:
            return streams

        try:
            dec_resp = http_post(
                DECRYPT_URL,
                content=json.dumps({"text": raw_text, "id": tmdb_id or "0"}),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            dec_data = dec_resp.json() if dec_resp else {}
        except:
            return streams

        if dec_data.get("status") != 200:
            return streams

        result = dec_data.get("result", {})

        for s in result.get("sources", []):
            s_url = s.get("url", "")
            quality = s.get("quality", "HD")
            if s_url:
                streams.append({
                    "url": s_url,
                    "quality": quality,
                    "provider": f"CineStream-{source['name']}",
                    "format": "mp4",
                })

        main_url = result.get("url", "")
        if main_url and not streams:
            streams.append({
                "url": main_url,
                "quality": "HD",
                "provider": f"CineStream-{source['name']}",
                "format": "mp4",
            })

    except Exception as e:
        pass

    return streams

def cinestream(title: str, media_type: str = "movie", year: str = "", tmdb_id: str = "", imdb_id: str = "", season: int = 0, episode: int = 0) -> list[dict]:
    sources = []

    for src in SOURCES:
        if src.get("movie_only") and media_type != "movie":
            continue

        season_id = str(season) if season > 0 else ""
        episode_id = str(episode) if episode > 0 else ""

        resolved = _resolve_source(
            src,
            title,
            media_type,
            year=year,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            season_id=season_id,
            episode_id=episode_id,
        )
        sources.extend(resolved)

    return sources
