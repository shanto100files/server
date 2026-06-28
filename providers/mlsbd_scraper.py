"""
MLSBD Pre-Scraper (Hybrid Approach)
Extracts metadata + savelinks.me IDs from MLSBD posts.
Savelinks contain GDFlix/HubCloud links (like cinecloud).
"""
import re
import asyncio
import aiosqlite
import json
import time
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache.db")

# MLSBD domains
MLSBD_DOMAINS = ["https://mlsbd.co", "https://www.mlsbd.com", "https://mlsbd.com"]

_stats = {"scraped": 0, "links": 0, "failed": 0, "last_run": None, "running": False}

async def init_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mlsbd_posts (
                url TEXT PRIMARY KEY,
                title TEXT,
                year TEXT,
                language TEXT,
                quality TEXT,
                resolution TEXT,
                size TEXT,
                genre TEXT,
                imdb_rating TEXT,
                storyline TEXT,
                savelinks_ids TEXT,
                last_scraped REAL
            )
        """)
        await db.commit()

async def get_scraped_urls():
    async with aiosqlite.connect(DB_PATH) as db:
        urls = set()
        async with db.execute("SELECT url FROM mlsbd_posts") as cursor:
            async for row in cursor:
                urls.add(row[0])
        return urls

async def save_post(url, title, year, language, quality, resolution, size, genre, imdb_rating, storyline, savelinks_ids):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO mlsbd_posts 
            (url, title, year, language, quality, resolution, size, genre, imdb_rating, storyline, savelinks_ids, last_scraped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (url, title, year, language, quality, resolution, size, genre, imdb_rating, storyline, 
              json.dumps(savelinks_ids), time.time()))
        await db.commit()

async def fetch_html(url):
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
    """Get post URLs from MLSBD sitemap."""
    urls = []
    
    for domain in MLSBD_DOMAINS:
        # Try sitemap_index
        html = await fetch_html(f"{domain}/sitemap_index.xml")
        if html:
            sitemap_urls = re.findall(r'<loc>(.*?)</loc>', html)
            for sm_url in sitemap_urls:
                if "post-sitemap" in sm_url:
                    sm_html = await fetch_html(sm_url)
                    if sm_html:
                        post_urls = re.findall(r'<loc>(.*?)</loc>', sm_html)
                        urls.extend([u for u in post_urls if domain.replace("https://", "") in u])
            if urls:
                break
    
    return list(set(urls))

def extract_metadata(html):
    """Extract detailed metadata from MLSBD page."""
    title = ""
    year = ""
    language = ""
    quality = ""
    resolution = ""
    size = ""
    genre = ""
    imdb_rating = ""
    storyline = ""
    
    # Title
    m = re.search(r'<title>(.*?)</title>', html)
    if m:
        title = m.group(1).split('–')[0].split('–')[0].strip()
    
    # Year
    m = re.search(r'(\d{4})', title)
    if m:
        year = m.group(1)
    
    # Language (from metadata section)
    m = re.search(r'Language\s*:\s*(.*?)(?:\n|<|$)', html)
    if m:
        language = m.group(1).strip()
    
    # Quality
    m = re.search(r'Quality\s*:\s*(.*?)(?:\n|<|$)', html)
    if m:
        quality = m.group(1).strip()
    
    # Resolution
    m = re.search(r'Resolution\s*:\s*(.*?)(?:\n|<|$)', html)
    if m:
        resolution = m.group(1).strip()
    
    # Size
    m = re.search(r'Size\s*:\s*(.*?)(?:\n|<|$)', html)
    if m:
        size = m.group(1).strip()
    
    # Genre
    m = re.search(r'Genres?\s*:\s*(.*?)(?:\n|<|$)', html)
    if m:
        genre = m.group(1).strip()
    
    # IMDb Rating
    m = re.search(r'IMDb\s*Ratings?\s*:\s*(.*?)(?:\n|<|$)', html)
    if m:
        imdb_rating = m.group(1).strip()
    
    # Storyline
    m = re.search(r'Storyline\s*:\s*(.*?)(?:\n|<|$)', html)
    if m:
        storyline = m.group(1).strip()
    
    return title, year, language, quality, resolution, size, genre, imdb_rating, storyline

def extract_savelinks(html):
    """Extract savelinks.me IDs from HTML."""
    savelinks_ids = []
    
    # Find savelinks.me URLs
    pattern = r'https?://savelinks\.me/(?:view/)?([A-Za-z0-9]+)'
    matches = re.findall(pattern, html)
    
    for match in matches:
        if match not in savelinks_ids:
            savelinks_ids.append(match)
    
    return savelinks_ids

async def scrape_post(url):
    global _stats
    
    try:
        html = await fetch_html(url)
        if not html:
            _stats["failed"] += 1
            return None
        
        title, year, language, quality, resolution, size, genre, imdb_rating, storyline = extract_metadata(html)
        savelinks_ids = extract_savelinks(html)
        
        if not title:
            _stats["failed"] += 1
            return None
        
        _stats["scraped"] += 1
        _stats["links"] += len(savelinks_ids)
        
        return {
            "url": url,
            "title": title,
            "year": year,
            "language": language,
            "quality": quality,
            "resolution": resolution,
            "size": size,
            "genre": genre,
            "imdb_rating": imdb_rating,
            "storyline": storyline,
            "savelinks_ids": savelinks_ids
        }
        
    except Exception as e:
        _stats["failed"] += 1
        return None

async def run_scraper(max_posts=500):
    global _stats
    
    if _stats["running"]:
        return
    
    _stats["running"] = True
    _stats["last_run"] = datetime.now().isoformat()
    
    print(f"[MLSBD Scraper] Starting at {datetime.now()}")
    
    await init_table()
    
    sitemap_urls = await get_sitemap_urls()
    if not sitemap_urls:
        print("[MLSBD Scraper] Failed to fetch sitemap")
        _stats["running"] = False
        return
    
    print(f"[MLSBD Scraper] Found {len(sitemap_urls)} URLs")
    
    scraped_urls = await get_scraped_urls()
    new_urls = [u for u in sitemap_urls if u not in scraped_urls]
    
    print(f"[MLSBD Scraper] Already: {len(scraped_urls)}, New: {len(new_urls)}")
    
    urls = new_urls[:max_posts]
    if not urls:
        _stats["running"] = False
        return
    
    sem = asyncio.Semaphore(5)
    
    async def _scrape_one(url):
        async with sem:
            result = await scrape_post(url)
            if result:
                await save_post(
                    result["url"], result["title"], result["year"],
                    result["language"], result["quality"], result["resolution"],
                    result["size"], result["genre"], result["imdb_rating"],
                    result["storyline"], result["savelinks_ids"]
                )
            await asyncio.sleep(0.5)
            return result
    
    batch_size = 20
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i+batch_size]
        tasks = [_scrape_one(url) for url in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful = sum(1 for r in results if r and not isinstance(r, Exception))
        print(f"[MLSBD Scraper] Batch {i//batch_size + 1}: {successful}/{len(batch)}")
    
    _stats["running"] = False
    print(f"[MLSBD Scraper] Done! {_stats['scraped']} scraped, {_stats['links']} links")

def get_stats():
    return _stats.copy()

async def search_pre_scraped(query):
    async with aiosqlite.connect(DB_PATH) as db:
        results = []
        search_term = f"%{query}%"
        async with db.execute(
            "SELECT * FROM mlsbd_posts WHERE title LIKE ? LIMIT 10",
            (search_term,)
        ) as cursor:
            async for row in cursor:
                results.append({
                    "url": row[0],
                    "title": row[1],
                    "year": row[2],
                    "language": row[3],
                    "quality": row[4],
                    "resolution": row[5],
                    "size": row[6],
                    "genre": row[7],
                    "imdb_rating": row[8],
                    "storyline": row[9],
                    "savelinks_ids": json.loads(row[10]) if row[10] else []
                })
        return results

async def resolve_savelink(savelink_id):
    """Resolve savelinks.me ID to get GDFlix/HubCloud links."""
    url = f"https://savelinks.me/view/{savelink_id}"
    html = await fetch_html(url)
    if not html:
        return []
    
    links = []
    
    # Extract GDFlix links
    gdflix_pattern = r'https?://(?:gdflix\.\w+|new\d+\.gdflix\.\w+)/file/[A-Za-z0-9]+'
    gdflix_links = re.findall(gdflix_pattern, html)
    for link in gdflix_links:
        if link not in links:
            links.append({"type": "gdflix", "url": link})
    
    # Extract HubCloud links
    hubcloud_pattern = r'https?://(?:hubcloud\.\w+|new\d+\.hubcloud\.\w+)/video/[A-Za-z0-9]+'
    hubcloud_links = re.findall(hubcloud_pattern, html)
    for link in hubcloud_links:
        if link not in links:
            links.append({"type": "hubcloud", "url": link})
    
    # Extract FilePress links
    filepress_pattern = r'https?://(?:filepress\.\w+|new\d+\.filepress\.\w+)/file/[A-Za-z0-9]+'
    filepress_links = re.findall(filepress_pattern, html)
    for link in filepress_links:
        if link not in links:
            links.append({"type": "filepress", "url": link})
    
    return links
