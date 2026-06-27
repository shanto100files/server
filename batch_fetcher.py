"""
Batch Fetcher — TMDB 2025 Movies/Series + Provider Link Storage

Flow:
  1. Fetch 2025 movies/series from TMDB (by genre/category)
  2. Store in SQLite (content_cache table)
  3. For each content, run providers → store intermediate links
  4. Next search → load from cache → fast!

Usage:
  python batch_fetcher.py                # fetch all
  python batch_fetcher.py --type movie   # only movies
  python batch_fetcher.py --type tv      # only series
  python batch_fetcher.py --genre 28     # only action (genre_id=28)
  python batch_fetcher.py --pages 5      # 5 pages per genre
"""

import asyncio
import httpx
import json
import time
import os
import sys
import argparse
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "6a22df4196745281fa0beba769ad867f")
TMDB_BASE = "https://api.themoviedb.org/3"

DB_PATH = os.path.join(os.path.dirname(__file__), "cache.db")

# 2025 genres
GENRES_MOVIE = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
    9648: "Mystery", 10749: "Romance", 878: "Sci-Fi", 53: "Thriller",
    10752: "War", 37: "Western",
}

GENRES_TV = {
    10759: "Action & Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    10762: "Kids", 9648: "Mystery", 10763: "News", 10764: "Reality",
    10765: "Sci-Fi & Fantasy", 10766: "Soap", 10767: "Talk",
    10768: "War & Politics", 37: "Western",
}

# All providers
PROVIDERS = [
    "cinefreak", "hdhub4u", "mlsbd", "southfreak", "bollyflix",
    "vegamovies", "fourkhd",
]

import aiosqlite


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS content_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tmdb_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                media_type TEXT NOT NULL,
                year TEXT DEFAULT '',
                rating REAL DEFAULT 0,
                genres TEXT DEFAULT '',
                description TEXT DEFAULT '',
                poster_url TEXT DEFAULT '',
                backdrop_url TEXT DEFAULT '',
                fetched_at REAL NOT NULL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_cache_tmdb
            ON content_cache(tmdb_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_cache_type
            ON content_cache(media_type)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_cache_fetched
            ON content_cache(fetched_at)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scraped_content (
                tmdb_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                media_type TEXT NOT NULL,
                scraped_at REAL NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scraped_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tmdb_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                media_type TEXT NOT NULL,
                url TEXT NOT NULL,
                quality TEXT DEFAULT 'HD',
                provider TEXT DEFAULT '',
                format TEXT DEFAULT 'mp4',
                episode_label TEXT DEFAULT '',
                file_size TEXT DEFAULT '',
                language TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_scraped_links_tmdb
            ON scraped_links(tmdb_id)
        """)
        await db.commit()


async def fetch_tmdb_page(media_type: str, genre_id: int, page: int = 1) -> list[dict]:
    """Fetch one page of TMDB discover results."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{TMDB_BASE}/discover/{media_type}",
            params={
                "api_key": TMDB_API_KEY,
                "language": "en-US",
                "sort_by": "popularity.desc",
                "with_genres": str(genre_id),
                "primary_release_year" if media_type == "movie" else "first_air_date_year": 2025,
                "page": page,
                "vote_count.gte": 10,
            },
        )
        if r.status_code != 200:
            return []
        data = r.json()
        results = []
        for item in data.get("results", [])[:20]:
            title = item.get("title") or item.get("name", "")
            year = (item.get("release_date") or item.get("first_air_date") or "")[:4]
            if not title:
                continue
            results.append({
                "tmdb_id": item["id"],
                "title": title,
                "media_type": media_type,
                "year": year,
                "rating": round(item.get("vote_average", 0), 1),
                "genres": str(genre_id),
                "description": item.get("overview", ""),
                "poster_url": f"https://image.tmdb.org/t/p/w500{item.get('poster_path', '')}" if item.get("poster_path") else "",
                "backdrop_url": f"https://image.tmdb.org/t/p/w1280{item.get('backdrop_path', '')}" if item.get("backdrop_path") else "",
            })
        return results


async def fetch_all_2025(media_type: str = None, genre_id: int = None, pages_per_genre: int = 3) -> list[dict]:
    """Fetch all 2025 content from TMDB."""
    all_content = []
    seen_ids = set()

    genres = GENRES_MOVIE if media_type == "movie" else GENRES_TV
    if media_type is None:
        genres = {**GENRES_MOVIE, **GENRES_TV}

    types_to_fetch = [media_type] if media_type else ["movie", "tv"]

    for mt in types_to_fetch:
        g = GENRES_MOVIE if mt == "movie" else GENRES_TV
        if genre_id:
            g = {genre_id: g.get(genre_id, f"Genre-{genre_id}")}

        for gid, gname in g.items():
            print(f"  Fetching {mt} / {gname} (genre {gid})...")
            for page in range(1, pages_per_genre + 1):
                try:
                    items = await fetch_tmdb_page(mt, gid, page)
                    for item in items:
                        if item["tmdb_id"] not in seen_ids:
                            seen_ids.add(item["tmdb_id"])
                            item["genre_name"] = gname
                            all_content.append(item)
                    if len(items) < 10:
                        break
                    await asyncio.sleep(0.3)
                except Exception as e:
                    print(f"    Error: {e}")
                    break

    return all_content


async def save_content(content_list: list[dict]):
    """Save content to database."""
    async with aiosqlite.connect(DB_PATH) as db:
        saved = 0
        for item in content_list:
            try:
                await db.execute(
                    """INSERT OR IGNORE INTO content_cache
                    (tmdb_id, title, media_type, year, rating, genres, description, poster_url, backdrop_url, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (item["tmdb_id"], item["title"], item["media_type"],
                     item["year"], item["rating"], item.get("genre_name", ""),
                     item["description"], item["poster_url"], item["backdrop_url"],
                     time.time())
                )
                saved += 1
            except Exception:
                pass
        await db.commit()
        return saved


async def get_unscraped_content(limit: int = 50) -> list[dict]:
    """Get content that hasn't been scraped yet."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if scraped_content table exists
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scraped_content (
                tmdb_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                media_type TEXT NOT NULL,
                scraped_at REAL NOT NULL
            )
        """)
        await db.commit()

        rows = []
        async with db.execute(
            """SELECT cc.tmdb_id, cc.title, cc.media_type, cc.year
            FROM content_cache cc
            LEFT JOIN scraped_content sc ON cc.tmdb_id = sc.tmdb_id
            WHERE sc.tmdb_id IS NULL
            LIMIT ?""",
            (limit,)
        ) as cursor:
            async for row in cursor:
                rows.append({
                    "tmdb_id": row[0],
                    "title": row[1],
                    "media_type": row[2],
                    "year": row[3],
                })
        return rows


async def mark_scraped(tmdb_id: int, title: str, media_type: str):
    """Mark content as scraped."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO scraped_content (tmdb_id, title, media_type, scraped_at) VALUES (?, ?, ?, ?)",
            (tmdb_id, title, media_type, time.time())
        )
        await db.commit()


async def save_scraped_links(tmdb_id: int, title: str, media_type: str, sources: list[dict]):
    """Save scraped links to database — only DIRECT playable links."""
    import re
    if not sources:
        return

    # Only store these — direct playable links
    DIRECT_PATTERNS = [
        r'\.m3u8', r'\.mpd', r'\.mp4', r'\.mkv',
        r'r2\.dev', r'r2\.cloudflarestorage',
        r'google\.com/drive', r'googleusercontent\.com',
        r'pixeldrain\.(com|dev)',
        r'workers\.dev', r'pages\.dev',
        r'blob\.core\.windows\.net',
        r'mediafire\.com',
        r'cloudflare-d\.', r'cloudserver-',
        r'ddl2\.', r'dolic', r'rosed', r'naceral',
        r'tiny-king', r'lingering-shadow',
    ]

    # Skip these — intermediate links that need resolution
    SKIP_PATTERNS = [
        r'hubcloud\.cx', r'hubcloud\.com', r'hub\.cloud',
        r'gofile\.io', r'drivebot', r'fastdlserver',
        r'bit\.ly', r'whistle\.lat', r'noirspy',
        r'hubdrive', r'gdxshare',
        r'hub\.latent\.click', r'hub\.pyramid\.surf',
        r'gpdl2\.', r'fast-dl\.one',
    ]

    def is_direct_playable(url: str) -> bool:
        url_lower = url.lower()
        # Skip intermediate links
        for pat in SKIP_PATTERNS:
            if re.search(pat, url_lower):
                return False
        # Must match direct pattern
        for pat in DIRECT_PATTERNS:
            if re.search(pat, url_lower):
                return True
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        saved = 0
        for s in sources:
            url = s.get("url", "")
            if not url or not is_direct_playable(url):
                continue
            await db.execute(
                """INSERT INTO scraped_links
                (tmdb_id, title, media_type, url, quality, provider, format, episode_label, file_size, language, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (tmdb_id, title, media_type, url,
                 s.get("quality", "HD"), s.get("provider", ""), s.get("format", "mp4"),
                 s.get("episode_label", ""), s.get("file_size", ""), s.get("language", ""),
                 time.time())
            )
            saved += 1
        await db.commit()
        return saved


async def scrape_content_links(tmdb_id: int, title: str, media_type: str) -> list[dict]:
    """Run all providers for one content item and return sources."""
    sys.path.insert(0, os.path.dirname(__file__))
    from providers.cinefreak import cinefreak
    from providers.hdhub4u import hdhub4u
    from providers.mlsbd import mlsbd
    from providers.southfreak import southfreak
    from providers.bollyflix import bollyflix
    from providers.vegamovies import vegamovies
    from providers.fourkhd import fourkhd

    all_sources = []

    provider_funcs = [
        ("cinefreak", cinefreak, (str(tmdb_id), media_type, title, 0, 0)),
        ("hdhub4u", hdhub4u, (title, str(tmdb_id))),
        ("mlsbd", mlsbd, (title, str(tmdb_id))),
        ("southfreak", southfreak, (title, str(tmdb_id))),
        ("bollyflix", bollyflix, (title, str(tmdb_id))),
        ("vegamovies", vegamovies, (title, str(tmdb_id), 0, 0, "", media_type)),
        ("fourkhd", fourkhd, (title, str(tmdb_id))),
    ]

    async def run_one(name, func, args):
        try:
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(func(*args), timeout=25)
            else:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: func(*args)),
                    timeout=25
                )
            return name, result or []
        except Exception:
            return name, []

    # Run with semaphore (max 4 concurrent)
    sem = asyncio.Semaphore(4)
    async def limited(name, func, args):
        async with sem:
            return await run_one(name, func, args)

    tasks = [limited(n, f, a) for n, f, a in provider_funcs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen = set()
    for r in results:
        if isinstance(r, tuple):
            name, sources = r
            for s in sources:
                url = s.get("url", "").split("?")[0].rstrip("/")
                if url and url not in seen:
                    seen.add(url)
                    all_sources.append(s)

    return all_sources


async def batch_scrape(limit: int = 50, concurrency: int = 8):
    """Scrape links for unscraped content — PARALLEL."""
    items = await get_unscraped_content(limit)
    if not items:
        print("No unscraped content found!")
        return

    print(f"\nScraping {len(items)} items ({concurrency} parallel)...")

    total_links = 0
    completed = 0
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()

    async def scrape_one(item):
        nonlocal total_links, completed
        tmdb_id = item["tmdb_id"]
        title = item["title"]
        media_type = item["media_type"]
        safe_title = title.encode('ascii', 'replace').decode('ascii')

        async with sem:
            try:
                sources = await scrape_content_links(tmdb_id, title, media_type)
                async with lock:
                    total_links += len(sources)
                    completed += 1
                    print(f"  [{completed}/{len(items)}] {safe_title} -> {len(sources)} links", flush=True)
                await mark_scraped(tmdb_id, title, media_type)
                await save_scraped_links(tmdb_id, title, media_type, sources)
            except Exception as e:
                async with lock:
                    completed += 1
                    print(f"  [{completed}/{len(items)}] {safe_title} -> Error: {e}", flush=True)

    # Run all in parallel
    tasks = [scrape_one(item) for item in items]
    await asyncio.gather(*tasks)

    print(f"\nDone! Total links found: {total_links}")


async def show_stats():
    """Show database stats."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Content cache
        async with db.execute("SELECT COUNT(*) FROM content_cache") as cursor:
            total_content = (await cursor.fetchone())[0]
        async with db.execute("SELECT media_type, COUNT(*) FROM content_cache GROUP BY media_type") as cursor:
            by_type = dict(await cursor.fetchall())

        # Scraped content
        try:
            async with db.execute("SELECT COUNT(*) FROM scraped_content") as cursor:
                scraped = (await cursor.fetchone())[0]
        except:
            scraped = 0

        # Link cache
        try:
            async with db.execute("SELECT COUNT(*) FROM link_cache") as cursor:
                total_links = (await cursor.fetchone())[0]
        except:
            total_links = 0

    print(f"\n=== Database Stats ===")
    print(f"Content cached: {total_content}")
    print(f"  Movies: {by_type.get('movie', 0)}")
    print(f"  TV Shows: {by_type.get('tv', 0)}")
    print(f"Scraped: {scraped}")
    print(f"Link cache: {total_links}")


# ===== D1 Push =====

D1_API_URL = os.environ.get("D1_API_URL", "https://cinepix-api.<account-id>.workers.dev")
D1_AUTH_TOKEN = os.environ.get("D1_AUTH_TOKEN", "")


async def push_to_d1(content_list: list[dict], batch_size: int = 20):
    """Push scraped content + links to D1 via Worker API."""
    if not D1_API_URL or not D1_AUTH_TOKEN:
        print("ERROR: D1_API_URL and D1_AUTH_TOKEN must be set in .env")
        print("  D1_API_URL=https://cinepix-api.YOUR-ACCOUNT.workers.dev")
        print("  D1_AUTH_TOKEN=your-admin-token")
        return False

    headers = {
        "Authorization": f"Bearer {D1_AUTH_TOKEN}",
        "Content-Type": "application/json",
    }

    total_pushed = 0
    total_links = 0

    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(content_list), batch_size):
            batch = content_list[i:i + batch_size]
            payload = {"content": batch}

            try:
                r = await client.post(
                    f"{D1_API_URL}/api/admin/bulk-import",
                    headers=headers,
                    json=payload,
                )
                if r.status_code in (200, 201):
                    data = r.json()
                    total_pushed += data.get("content_inserted", 0)
                    total_links += data.get("links_inserted", 0)
                    print(f"  Batch {i // batch_size + 1}: {data.get('content_inserted', 0)} content, {data.get('links_inserted', 0)} links")
                else:
                    print(f"  Batch {i // batch_size + 1}: Error {r.status_code} - {r.text[:100]}")
            except Exception as e:
                print(f"  Batch {i // batch_size + 1}: Error - {e}")

            await asyncio.sleep(0.5)

    print(f"\nD1 Push complete: {total_pushed} content, {total_links} links")
    return True


async def get_scraped_content_for_d1(limit: int = 100) -> list[dict]:
    """Get scraped content with links ready for D1 push."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Get content that has been scraped (has links)
        rows = []
        async with db.execute(
            """SELECT DISTINCT cc.tmdb_id, cc.title, cc.media_type, cc.year, cc.rating,
                      cc.genres, cc.description, cc.poster_url, cc.backdrop_url
            FROM content_cache cc
            INNER JOIN scraped_content sc ON cc.tmdb_id = sc.tmdb_id
            LIMIT ?""",
            (limit,)
        ) as cursor:
            async for row in cursor:
                tmdb_id = row[0]
                title = row[1]
                media_type = row[2]

                # Get links from scraped_links table
                link_rows = []
                try:
                    async with db.execute(
                        """SELECT url, quality, provider, format, episode_label, file_size, language
                        FROM scraped_links WHERE tmdb_id = ?""",
                        (tmdb_id,)
                    ) as lcur:
                        async for lrow in lcur:
                            link_rows.append({
                                "url": lrow[0],
                                "quality": lrow[1],
                                "type": "watch",
                                "provider": lrow[2],
                                "format": lrow[3],
                                "episode_label": lrow[4],
                                "file_size": lrow[5],
                                "language": lrow[6],
                            })
                except:
                    pass

                rows.append({
                    "tmdb_id": tmdb_id,
                    "title": title,
                    "media_type": media_type,
                    "year": row[3] or "",
                    "rating": row[4] or 0,
                    "genres": row[5] or "",
                    "description": row[6] or "",
                    "poster_url": row[7] or "",
                    "backdrop_url": row[8] or "",
                    "links": link_rows,
                })

        return rows


def main():
    parser = argparse.ArgumentParser(description="TMDB 2025 Batch Fetcher")
    parser.add_argument("--type", choices=["movie", "tv"], help="Only movies or TV")
    parser.add_argument("--genre", type=int, help="Only this genre ID")
    parser.add_argument("--pages", type=int, default=3, help="Pages per genre (default 3)")
    parser.add_argument("--scrape", action="store_true", help="Also scrape provider links")
    parser.add_argument("--scrape-only", action="store_true", help="Only scrape (skip TMDB fetch)")
    parser.add_argument("--push-d1", action="store_true", help="Push scraped data to D1 (Cloudflare)")
    parser.add_argument("--limit", type=int, default=50, help="Max items to scrape/push")
    parser.add_argument("--concurrency", type=int, default=8, help="Parallel workers (default 8)")
    parser.add_argument("--stats", action="store_true", help="Show stats only")
    args = parser.parse_args()

    async def run():
        await init_db()

        if args.stats:
            await show_stats()
            return

        if not args.scrape_only and not args.push_d1:
            print("Fetching 2025 content from TMDB...")
            content = await fetch_all_2025(args.type, args.genre, args.pages)
            print(f"Found {len(content)} items")

            saved = await save_content(content)
            print(f"Saved {saved} new items to database")

        if args.scrape or args.scrape_only:
            await batch_scrape(args.limit, args.concurrency)

        if args.push_d1:
            print(f"\nPushing to D1...")
            data = await get_scraped_content_for_d1(args.limit)
            if data:
                await push_to_d1(data)
            else:
                print("No scraped content to push!")

        await show_stats()

    asyncio.run(run())


if __name__ == "__main__":
    main()
