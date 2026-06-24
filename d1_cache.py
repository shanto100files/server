import os
import json
import time
import httpx
from typing import Optional, Dict, Any

# D1 API Configuration
D1_API_URL = os.environ.get("D1_API_URL", "https://cinepix-api.your-subdomain.workers.dev")

PROVIDER_TTL = {
    "cinefreak": 6 * 3600,
    "gdflix": 1 * 3600,
    "mlsbd": 3 * 3600,
    "hdhub4u": 2 * 3600,
    "movielinkbd": 3 * 3600,
    "vegamovies": 2 * 3600,
    "tmdb_search": 2 * 3600,
}

# Local fallback cache (in-memory)
_local_cache: Dict[str, Dict[str, Any]] = {}


async def init_db():
    """Initialize D1 connection (no-op for API-based approach)"""
    print(f"[D1] Using Cloudflare D1 API: {D1_API_URL}")


async def cache_get(key: str, provider: str) -> Optional[dict]:
    """Get cached data from D1 or local fallback"""
    # Try D1 first
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{D1_API_URL}/api/cache",
                params={"key": key, "provider": provider}
            )
            if resp.status_code == 200:
                data = resp.json()
                if data is not None:
                    return data
    except Exception as e:
        print(f"[D1] Cache get error: {e}")

    # Fallback to local cache
    if key in _local_cache:
        entry = _local_cache[key]
        ttl = PROVIDER_TTL.get(provider, 2 * 3600)
        if time.time() - entry["created_at"] < ttl:
            return entry["data"]
        else:
            del _local_cache[key]

    return None


async def cache_set(key: str, data: dict, provider: str):
    """Set cache data in D1 and local"""
    # Store locally
    _local_cache[key] = {
        "data": data,
        "provider": provider,
        "created_at": time.time()
    }

    # Store in D1
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{D1_API_URL}/api/cache",
                json={"key": key, "data": data, "provider": provider}
            )
    except Exception as e:
        print(f"[D1] Cache set error: {e}")


async def cache_stats() -> dict:
    """Get cache statistics from D1"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{D1_API_URL}/api/cache/stats")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"[D1] Cache stats error: {e}")

    # Fallback to local stats
    providers = {}
    for key, entry in _local_cache.items():
        p = entry.get("provider", "unknown")
        providers[p] = providers.get(p, 0) + 1

    return {
        "total_entries": len(_local_cache),
        "recent_1hr": sum(1 for e in _local_cache.values() if time.time() - e["created_at"] < 3600),
        "by_provider": providers
    }


async def cache_clear():
    """Clear all cache from D1 and local"""
    _local_cache.clear()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.delete(f"{D1_API_URL}/api/cache")
    except Exception as e:
        print(f"[D1] Cache clear error: {e}")
