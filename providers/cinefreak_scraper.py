"""
CineFreak Pre-Scraper
Background scraper that stores cinefreak posts + cinecloud links to SQLite.
Runs on server startup and periodically refreshes.
"""
import re
import base64
import asyncio
import aiosqlite
import json
import time
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache.db")
SITEMAP_URL = "https://cinefreak.net/post-sitemap.xml"
CINECLOUD_BASE = "https://new5.cinecloud.site"

# Stats
_stats = {"scraped": 0, "links": 0, "failed": 0, "last_run": None, "running": False}

async def init_pre_scrape_table():
    """Create cinefreak_posts table if not exists."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cinefreak_posts (
                url TEXT PRIMARY KEY,
                title TEXT,
                year TEXT,
                language TEXT,
                genre TEXT,
                imdb_rating TEXT,
                quality TEXT,
                cinecloud_links TEXT,
                last_scraped REAL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_cinefreak_title 
            ON cinefreak_posts(title)
        """)
        await db.commit()

async def get_scraped_urls():
    """Get already scraped URLs."""
    async with aiosqlite.connect(DB_PATH) as db:
        urls = set()
        async with db.execute("SELECT url FROM cinefreak_posts") as cursor:
            async for row in cursor:
                urls.add(row[0])
        return urls

async def save_post(url, title, year, language, genre, imdb_rating, quality, cinecloud_links):
    """Save a scraped post to database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO cinefreak_posts 
            (url, title, year, language, genre, imdb_rating, quality, cinecloud_links, last_scraped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (url, title, year, language, genre, imdb_rating, quality, 
              json.dumps(cinecloud_links), time.time()))
        await db.commit()

async def fetch_html(url):
    """Fetch HTML using httpx."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if r.status_code == 200:
                return r.text
    except:
        pass
    return None

async def get_sitemap_urls():
    """Get all post URLs from sitemap."""
    html = await fetch_html(SITEMAP_URL)
    if not html:
        return []
    
    # Parse sitemap XML
    urls = re.findall(r'<loc>(.*?)</loc>', html)
    # Filter only post URLs (exclude category, page URLs)
    post_urls = [u for u in urls if u.startswith("https://cinefreak.net/") and u != "https://cinefreak.net/"]
    return post_urls

def extract_metadata(html):
    """Extract metadata from cinefreak page HTML."""
    title = ""
    year = ""
    language = ""
    genre = ""
    imdb_rating = ""
    quality = ""
    
    # Title
    m = re.search(r'<title>(.*?)</title>', html)
    if m:
        title = m.group(1).split('|')[0].strip()
    
    # Year
    m = re.search(r'(\d{4})', title)
    if m:
        year = m.group(1)
    
    # IMDb
    m = re.search(r'IMDb Rating:\s*([\d.]+)', html)
    if m:
        imdb_rating = m.group(1)
    
    # Language
    m = re.search(r'Language:\s*(.*?)(?:\n|<)', html)
    if m:
        language = m.group(1).strip()
    
    # Genre
    m = re.search(r'Genres?:\s*(.*?)(?:\n|<)', html)
    if m:
        genre = m.group(1).strip()
    
    # Quality
    m = re.search(r'Quality:\s*(.*?)(?:\n|<)', html)
    if m:
        quality = m.group(1).strip()
    
    return title, year, language, genre, imdb_rating, quality

def extract_cinecloud_links(html):
    """Extract cinecloud links from HTML (base64 encoded in generate.php)."""
    links = []
    
    # Find generate.php links
    gen_links = re.findall(r'href=["\']([^"\']*generate\.php\?id=[^"\']+)["\']', html)
    
    for gen_url in gen_links:
        m = re.search(r'id=([A-Za-z0-9+/=]+)', gen_url)
        if m:
            try:
                decoded = base64.b64decode(m.group(1)).decode()
                if "cinecloud" in decoded.lower():
                    # Get quality/size from surrounding text
                    quality = ""
                    size = ""
                    
                    # Find the button text near this link
                    btn_pattern = rf'generate\.php\?id={re.escape(m.group(1))}[^"]*"[^>]*>([^<]*)<'
                    btn_match = re.search(btn_pattern, html)
                    if btn_match:
                        btn_text = btn_match.group(1)
                        q = re.search(r'(480p|720p|1080p|2160p|4K)', btn_text)
                        if q:
                            quality = q.group(1)
                    
                    # Find size in nearby text
                    size_pattern = r'\[([\d.]+ [GMK]B)\]'
                    size_matches = re.findall(size_pattern, html)
                    if size_matches:
                        size = size_matches[0] if size_matches else ""
                    
                    links.append({
                        "url": decoded,
                        "quality": quality,
                        "size": size,
                        "type": "download" if "/f/" in decoded else "watch"
                    })
            except:
                pass
    
    return links

async def scrape_post(url):
    """Scrape a single post and return data."""
    global _stats
    
    try:
        html = await fetch_html(url)
        if not html:
            _stats["failed"] += 1
            return None
        
        title, year, language, genre, imdb_rating, quality = extract_metadata(html)
        cinecloud_links = extract_cinecloud_links(html)
        
        if not title:
            _stats["failed"] += 1
            return None
        
        _stats["scraped"] += 1
        _stats["links"] += len(cinecloud_links)
        
        return {
            "url": url,
            "title": title,
            "year": year,
            "language": language,
            "genre": genre,
            "imdb_rating": imdb_rating,
            "quality": quality,
            "cinecloud_links": cinecloud_links
        }
        
    except Exception as e:
        _stats["failed"] += 1
        return None

async def run_scraper(max_posts=100):
    """Main scraper loop."""
    global _stats
    
    if _stats["running"]:
        return
    
    _stats["running"] = True
    _stats["last_run"] = datetime.now().isoformat()
    
    print(f"[CineFreak Scraper] Starting at {datetime.now()}")
    
    await init_pre_scrape_table()
    
    # Get sitemap URLs
    sitemap_urls = await get_sitemap_urls()
    if not sitemap_urls:
        print("[CineFreak Scraper] Failed to fetch sitemap")
        _stats["running"] = False
        return
    
    print(f"[CineFreak Scraper] Found {len(sitemap_urls)} URLs in sitemap")
    
    # Get already scraped URLs
    scraped_urls = await get_scraped_urls()
    new_urls = [u for u in sitemap_urls if u not in scraped_urls]
    
    print(f"[CineFreak Scraper] Already scraped: {len(scraped_urls)}, New: {len(new_urls)}")
    
    # Take only max_posts
    urls = new_urls[:max_posts]
    
    if not urls:
        print("[CineFreak Scraper] No new URLs to scrape")
        _stats["running"] = False
        return
    
    # Scrape with concurrency limit
    sem = asyncio.Semaphore(5)
    
    async def _scrape_one(url):
        async with sem:
            result = await scrape_post(url)
            if result:
                await save_post(
                    result["url"], result["title"], result["year"],
                    result["language"], result["genre"], result["imdb_rating"],
                    result["quality"], result["cinecloud_links"]
                )
            await asyncio.sleep(0.5)  # Rate limit
            return result
    
    # Run in batches
    batch_size = 20
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i+batch_size]
        tasks = [_scrape_one(url) for url in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = sum(1 for r in results if r and not isinstance(r, Exception))
        print(f"[CineFreak Scraper] Batch {i//batch_size + 1}: {successful}/{len(batch)} scraped")
    
    _stats["running"] = False
    print(f"[CineFreak Scraper] Done! Total: {_stats['scraped']} scraped, {_stats['links']} links, {_stats['failed']} failed")

def get_stats():
    """Get scraper statistics."""
    return _stats.copy()

async def search_pre_scraped(query):
    """Search pre-scraped posts by title."""
    async with aiosqlite.connect(DB_PATH) as db:
        results = []
        search_term = f"%{query}%"
        async with db.execute(
            "SELECT * FROM cinefreak_posts WHERE title LIKE ? LIMIT 10",
            (search_term,)
        ) as cursor:
            async for row in cursor:
                results.append({
                    "url": row[0],
                    "title": row[1],
                    "year": row[2],
                    "language": row[3],
                    "genre": row[4],
                    "imdb_rating": row[5],
                    "quality": row[6],
                    "cinecloud_links": json.loads(row[7]) if row[7] else []
                })
        return results

# For running standalone
if __name__ == "__main__":
    asyncio.run(run_scraper(50))
