"""
Link Indexer — Pre-caches intermediate links (gdflix, hubcloud, etc.)
for fast resolution on repeat searches.

Flow:
  1. Provider scrape → extract gdflix/hubcloud/drivebot URLs → save to DB
  2. Next search → load cached URLs → resolve directly → skip scraping
"""
import aiosqlite
import json
import time
import os
import re
from urllib.parse import urlparse

DB_PATH = os.path.join(os.path.dirname(__file__), "cache.db")

LINK_TTL = 6 * 3600  # 6 hours — intermediate links expire after this

# Domains that are "intermediate" — need resolution to get final stream link
INTERMEDIATE_DOMAINS = [
    "gdflix", "hubcloud", "drivebot", "fastdlserver", "linksmod",
    "hubdrive", "direct-dl.lol", "gdxshare", "fxlinks", "techzed",
    "savelinks", "net52.cc", "cinecloud", "cinefreak", "new5.cinecloud",
    "neodrive", "gdflix.to", "new1.gdflix", "fast-dl.one",
]

# Domains that are already direct stream links — no need to cache these
DIRECT_DOMAINS = [
    "r2.dev", "r2.cloudflarestorage", "googleusercontent.com",
    "pixeldrain.com", "pixeldrain.dev", "workers.dev", "pages.dev",
    "blob.core.windows.net", "mediafire.com",
]

# MIME/extension patterns for direct streams
DIRECT_PATTERNS = re.compile(r'\.(mkv|mp4|m3u8|mpd)(?:\?|$)', re.IGNORECASE)


def _is_intermediate_url(url: str) -> bool:
    """Check if URL is an intermediate link that needs resolution."""
    if not url:
        return False
    url_lower = url.lower()
    # Skip direct stream links
    if DIRECT_PATTERNS.search(url_lower):
        return False
    for d in DIRECT_DOMAINS:
        if d in url_lower:
            return False
    # Check if it's an intermediate domain
    host = (urlparse(url).hostname or "").lower()
    for d in INTERMEDIATE_DOMAINS:
        if d in host:
            return True
    return False


def _extract_intermediate_links(sources: list[dict]) -> list[dict]:
    """Extract intermediate links from provider results."""
    links = []
    seen = set()
    for s in sources:
        url = s.get("url", "")
        if not url:
            continue
        if _is_intermediate_url(url):
            normalized = url.split("?")[0].rstrip("/")
            if normalized not in seen:
                seen.add(normalized)
                links.append({
                    "url": url,
                    "quality": s.get("quality", "HD"),
                    "provider": s.get("provider", ""),
                    "format": s.get("format", ""),
                    "language": s.get("language", ""),
                })
    return links


async def init_link_table():
    """Create the link_cache table if it doesn't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS link_cache (
                key TEXT PRIMARY KEY,
                links TEXT NOT NULL,
                provider TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_link_cache_provider
            ON link_cache(provider)
        """)
        await db.commit()


async def save_links(tmdb_id: int, media_type: str, title: str,
                     season: int, episode: int, sources: list[dict]):
    """Save intermediate links from provider results to cache."""
    links = _extract_intermediate_links(sources)
    if not links:
        return

    key = f"{tmdb_id}:{media_type}:{title.lower().strip()}:s{season}:e{episode}"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO link_cache (key, links, provider, created_at) VALUES (?, ?, ?, ?)",
            (key, json.dumps(links), "indexed", time.time())
        )
        await db.commit()


async def load_links(tmdb_id: int, media_type: str, title: str,
                     season: int, episode: int) -> list[dict] | None:
    """Load cached intermediate links for a movie/series.

    Returns list of link dicts if cached and not expired, else None.
    """
    key = f"{tmdb_id}:{media_type}:{title.lower().strip()}:s{season}:e{episode}"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT links, created_at FROM link_cache WHERE key = ?", (key,)
        ) as row:
            async for links_json, created_at in row:
                if time.time() - created_at < LINK_TTL:
                    return json.loads(links_json)
                else:
                    # Expired — delete
                    await db.execute("DELETE FROM link_cache WHERE key = ?", (key,))
                    await db.commit()
    return None


async def resolve_cached_links(links: list[dict]) -> list[dict]:
    """Resolve cached intermediate links using auto_resolver.

    Returns resolved direct stream links.
    """
    import asyncio
    from providers.auto_resolver import resolve_any

    resolved = []
    seen = set()

    async def _resolve_one(link):
        url = link.get("url", "")
        quality = link.get("quality", "HD")
        referer = ""
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, lambda: resolve_any(url, quality=quality, referer=referer)
            )
            return results or []
        except Exception:
            return []

    tasks = [_resolve_one(link) for link in links]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, list):
            for r in result:
                url = r.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    resolved.append(r)

    return resolved


async def get_cached_sources(tmdb_id: int, media_type: str, title: str,
                             season: int, episode: int) -> list[dict] | None:
    """Try to get sources from cached intermediate links.

    Returns resolved direct links if cache hit, None if miss.
    """
    links = await load_links(tmdb_id, media_type, title, season, episode)
    if not links:
        return None

    resolved = await resolve_cached_links(links)
    if resolved:
        return resolved
    return None


async def index_provider_results(tmdb_id: int, media_type: str, title: str,
                                  season: int, episode: int,
                                  provider_name: str, sources: list[dict]):
    """After a provider returns results, index the intermediate links."""
    if not sources:
        return
    await save_links(tmdb_id, media_type, title, season, episode, sources)


async def cache_stats():
    """Get link cache statistics."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM link_cache") as row:
            async for count in row:
                total = count
        async with db.execute(
            "SELECT COUNT(*) FROM link_cache WHERE created_at > ?",
            (time.time() - 3600,)
        ) as row:
            async for count in row:
                recent = count
        async with db.execute(
            "SELECT provider, COUNT(*) FROM link_cache GROUP BY provider"
        ) as row:
            providers = {}
            async for provider, count in row:
                providers[provider] = count
    return {
        "total_entries": total,
        "recent_1hr": recent,
        "by_provider": providers,
        "ttl_hours": LINK_TTL // 3600,
    }


async def clear_expired():
    """Remove expired entries from link cache."""
    cutoff = time.time() - LINK_TTL
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM link_cache WHERE created_at < ?", (cutoff,))
        deleted = cursor.rowcount
        await db.commit()
    return deleted
