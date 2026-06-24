import aiosqlite
import time
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "cache.db")

PROVIDER_TTL = {
    "cinefreak": 6 * 3600,
    "gdflix": 1 * 3600,
    "mlsbd": 3 * 3600,
    "hdhub4u": 2 * 3600,
    "movielinkbd": 3 * 3600,
    "vegamovies": 2 * 3600,
    "tmdb_search": 2 * 3600,
}

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
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

async def cache_get(key: str, provider: str) -> dict | None:
    ttl = PROVIDER_TTL.get(provider, 2 * 3600)
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO cache (key, data, provider, created_at) VALUES (?, ?, ?, ?)",
            (key, json.dumps(data), provider, time.time()),
        )
        await db.commit()

async def cache_stats() -> dict:
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
    return {"total_entries": total, "recent_1hr": recent, "by_provider": providers}

async def cache_clear():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cache")
        await db.commit()
