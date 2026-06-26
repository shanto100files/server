import aiosqlite
import time
import json
import os

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

DB_PATH = os.path.join(os.path.dirname(__file__), "cache.db")

PROVIDER_TTL = {
    "cinefreak": 12 * 3600,
    "gdflix": 2 * 3600,
    "mlsbd": 6 * 3600,
    "hdhub4u": 4 * 3600,
    "movielinkbd": 6 * 3600,
    "vegamovies": 4 * 3600,
    "tmdb_search": 4 * 3600,
    "sources": 4 * 3600,
}

_redis = None
_use_redis = False

async def init_db():
    global _redis, _use_redis
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            _redis = aioredis.from_url(redis_url, decode_responses=True, max_connections=20)
            await _redis.ping()
            _use_redis = True
            print("[Cache] Redis connected: " + redis_url[:30] + "...")
        except Exception as e:
            print("[Cache] Redis unavailable, using SQLite: " + str(e)[:50])
            _use_redis = False
    if not _use_redis:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS link_cache (
                    url TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            await db.commit()
        print("[Cache] SQLite fallback ready")

async def cache_get(key: str, provider: str) -> dict | None:
    ttl = PROVIDER_TTL.get(provider, 4 * 3600)
    if _use_redis and _redis:
        try:
            raw = await _redis.get("cache:" + key)
            if raw:
                return json.loads(raw)
            return None
        except Exception:
            pass
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT data, created_at FROM cache WHERE key = ?", (key,)
        ) as row:
            async for data, created_at in row:
                if time.time() - created_at < ttl:
                    return json.loads(data)
                else:
                    await db.execute("DELETE FROM cache WHERE key = ?", (key,))
                    await db.commit()
    return None

async def cache_set(key: str, data: dict, provider: str):
    ttl = PROVIDER_TTL.get(provider, 4 * 3600)
    if _use_redis and _redis:
        try:
            await _redis.set("cache:" + key, json.dumps(data), ex=ttl)
            return
        except Exception:
            pass
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO cache (key, data, provider, created_at) VALUES (?, ?, ?, ?)",
            (key, json.dumps(data), provider, time.time()),
        )
        await db.commit()

async def cache_stats() -> dict:
    if _use_redis and _redis:
        try:
            info = await _redis.info("keyspace")
            total = 0
            for db_info in info.values():
                total += db_info.get("keys", 0)
            return {"total_entries": total, "recent_1hr": "N/A (Redis)", "by_provider": {}, "backend": "redis"}
        except Exception:
            pass
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM cache") as row:
            async for count in row:
                total = count
        async with db.execute(
            "SELECT provider, COUNT(*) FROM cache GROUP BY provider"
        ) as row:
            providers = {}
            async for provider, count in row:
                providers[provider] = count
        async with db.execute(
            "SELECT COUNT(*) FROM cache WHERE created_at > ?",
            (time.time() - 3600,),
        ) as row:
            async for count in row:
                recent = count
    return {"total_entries": total, "recent_1hr": recent, "by_provider": providers, "backend": "sqlite"}

async def cache_clear():
    if _use_redis and _redis:
        try:
            keys = []
            async for key in _redis.scan_iter("cache:*"):
                keys.append(key)
            if keys:
                await _redis.delete(*keys)
            return
        except Exception:
            pass
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cache")
        await db.commit()
