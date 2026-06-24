import httpx
import os
from cache import cache_get, cache_set

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "6a22df4196745281fa0beba769ad867f")
TMDB_BASE = "https://api.themoviedb.org/3"

async def search_tmdb(query: str) -> list[dict]:
    cached = await cache_get(f"tmdb:{query}", "tmdb_search")
    if cached:
        return cached

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{TMDB_BASE}/search/multi",
            params={"query": query, "api_key": TMDB_API_KEY, "language": "en-US"},
        )
        if r.status_code != 200:
            return []
        data = r.json()
        results = []
        for item in data.get("results", [])[:10]:
            if item.get("media_type") not in ("movie", "tv"):
                continue
            title = item.get("title") or item.get("name", "")
            year = (item.get("release_date") or item.get("first_air_date") or "")[:4]
            results.append({
                "id": item["id"],
                "title": title,
                "year": year,
                "type": item["media_type"],
                "poster": f"https://image.tmdb.org/t/p/w500{item.get('poster_path', '')}" if item.get("poster_path") else "",
                "rating": item.get("vote_average", 0),
            })
        await cache_set(f"tmdb:{query}", results, "tmdb_search")
        return results

async def get_movie_details(tmdb_id: int) -> dict | None:
    cached = await cache_get(f"tmdb_movie:{tmdb_id}", "tmdb_search")
    if cached:
        return cached

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{TMDB_BASE}/movie/{tmdb_id}",
            params={"api_key": TMDB_API_KEY, "language": "en-US"},
        )
        if r.status_code != 200:
            return None
        item = r.json()
        result = {
            "id": item["id"],
            "title": item.get("title", ""),
            "year": (item.get("release_date") or "")[:4],
            "type": "movie",
            "rating": item.get("vote_average", 0),
            "overview": item.get("overview", ""),
        }
        await cache_set(f"tmdb_movie:{tmdb_id}", result, "tmdb_search")
        return result

async def get_tv_details(tmdb_id: int, season: int = 0, episode: int = 0) -> dict | None:
    cached = await cache_get(f"tmdb_tv:{tmdb_id}:s{season}:e{episode}", "tmdb_search")
    if cached:
        return cached

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{TMDB_BASE}/tv/{tmdb_id}",
            params={"api_key": TMDB_API_KEY, "language": "en-US"},
        )
        if r.status_code != 200:
            return None
        item = r.json()
        seasons = []
        for s in item.get("seasons", []):
            if s.get("season_number", 0) == 0:
                continue
            seasons.append({
                "season_number": s["season_number"],
                "name": s.get("name", f"Season {s['season_number']}"),
                "episode_count": s.get("episode_count", 0),
                "poster": f"https://image.tmdb.org/t/p/w200{s.get('poster_path', '')}" if s.get("poster_path") else "",
            })
        result = {
            "id": item["id"],
            "title": item.get("name", ""),
            "year": (item.get("first_air_date") or "")[:4],
            "type": "tv",
            "rating": item.get("vote_average", 0),
            "overview": item.get("overview", ""),
            "season": season,
            "episode": episode,
            "seasons": seasons,
            "total_seasons": len(seasons),
        }
        await cache_set(f"tmdb_tv:{tmdb_id}:s{season}:e{episode}", result, "tmdb_search")
        return result

async def get_tv_season(tmdb_id: int, season: int) -> list[dict]:
    cached = await cache_get(f"tmdb_tv:{tmdb_id}:s{season}", "tmdb_season")
    if cached:
        return cached

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{TMDB_BASE}/tv/{tmdb_id}/season/{season}",
            params={"api_key": TMDB_API_KEY, "language": "en-US"},
        )
        if r.status_code != 200:
            return []
        data = r.json()
        episodes = []
        for ep in data.get("episodes", []):
            episodes.append({
                "episode_number": ep["episode_number"],
                "name": ep.get("name", f"Episode {ep['episode_number']}"),
                "overview": ep.get("overview", ""),
                "still": f"https://image.tmdb.org/t/p/w300{ep.get('still_path', '')}" if ep.get("still_path") else "",
            })
        await cache_set(f"tmdb_tv:{tmdb_id}:s{season}", episodes, "tmdb_season")
        return episodes
