"""
BollyFlix Pre-Scraper (Hybrid Approach)
Extracts metadata + fastdlserver IDs from BollyFlix posts.
fastdlserver redirects to GDFlix (like cinecloud/savelinks).
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

# BollyFlix domains
BOLLYFLIX_DOMAINS = ["https://new.bollyflix.med", "https://bollyflix.med"]

_stats = {"scraped": 0, "links": 0, "failed": 0, "last_run": None, "running": False}

async def init_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bollyflix_posts (
                url TEXT PRIMARY KEY,
                title TEXT,
                year TEXT,
                language TEXT,
                quality TEXT,
                size TEXT,
                genre TEXT,
                imdb_rating TEXT,
                cast TEXT,
                storyline TEXT,
                download_links TEXT,
                last_scraped REAL
            )
        """)
        await db.commit()

async def get_scraped_urls():
    async with aiosqlite.connect(DB_PATH) as db:
        urls = set()
        async with db.execute("SELECT url FROM bollyflix_posts") as cursor:
            async for row in cursor:
                urls.add(row[0])
        return urls

async def save_post(url, title, year, language, quality, size, genre, imdb_rating, cast, storyline, download_links):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO bollyflix_posts 
            (url, title, year, language, quality, size, genre, imdb_rating, cast, storyline, download_links, last_scraped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (url, title, year, language, quality, size, genre, imdb_rating, cast, storyline,
              json.dumps(download_links), time.time()))
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
    """Get post URLs from BollyFlix sitemap."""
    urls = []
    
    for domain in BOLLYFLIX_DOMAINS:
        html = await fetch_html(f"{domain}/sitemap.xml")
        if html:
            found = re.findall(r'<loc>(.*?)</loc>', html)
            urls.extend([u for u in found if "bollyflix" in u])
        
        # Also try post-sitemap
        html = await fetch_html(f"{domain}/post-sitemap.xml")
        if html:
            found = re.findall(r'<loc>(.*?)</loc>', html)
            urls.extend([u for u in found if "bollyflix" in u])
    
    return list(set(urls))

def extract_metadata(html):
    """Extract detailed metadata from BollyFlix page."""
    title = ""
    year = ""
    language = ""
    quality = ""
    size = ""
    genre = ""
    imdb_rating = ""
    cast = ""
    storyline = ""
    
    # Title from h1
    m = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h1>', html)
    if m:
        title = m.group(1).strip()
    else:
        m = re.search(r'<title>(.*?)</title>', html)
        if m:
            title = m.group(1).split('–')[0].split('|')[0].strip()
    
    # Year
    m = re.search(r'(\d{4})', title)
    if m:
        year = m.group(1)
    
    # Language (from metadata or title)
    m = re.search(r'Language:\s*(.*?)(?:\n|<|$)', html)
    if m:
        language = m.group(1).strip()
    else:
        # Fallback: extract from title
        lang_patterns = [
            r'(Dual Audio\s*\[.*?\])',
            r'(Hindi Dubbed)',
            r'(Bengali)',
            r'(Hindi)',
            r'(English)',
            r'(Tamil)',
            r'(Telugu)',
        ]
        for pattern in lang_patterns:
            m = re.search(pattern, title, re.IGNORECASE)
            if m:
                language = m.group(1)
                break
    
    # Quality
    m = re.search(r'Quality:\s*(.*?)(?:\n|<|$)', html)
    if m:
        quality = m.group(1).strip()
    
    # Size
    m = re.search(r'Size:\s*(.*?)(?:\n|<|$)', html)
    if m:
        size = m.group(1).strip()
    
    # Genre
    m = re.search(r'Genres?:\s*(.*?)(?:\n|<|$)', html)
    if m:
        genre = m.group(1).strip()
    
    # IMDb Rating
    m = re.search(r'imdb_rating["\']?\s*>\s*([\d.]+)', html)
    if m:
        imdb_rating = m.group(1)
    
    # Cast
    m = re.search(r'Cast(?:\(s\))?:\s*(.*?)(?:\n|<|$)', html)
    if m:
        cast = m.group(1).strip()
    
    # Storyline
    m = re.search(r'Storyline:\s*(.*?)(?:\n|<|$)', html)
    if m:
        storyline = m.group(1).strip()
    
    return title, year, language, quality, size, genre, imdb_rating, cast, storyline

def extract_download_links(html):
    """Extract fastdlserver and linksmod URLs from HTML."""
    links = []
    
    # Pattern for quality sections: <h5>...480p...</h5> followed by links
    # Find all download link pairs
    pattern = r'<h5[^>]*>.*?(\d{3,4}p).*?\[(.*?)\].*?</h5>.*?href=["\']([^"\']*fastdlserver[^"\']*)["\']'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
    
    for quality, size, fastdl_url in matches:
        # Extract base64 ID from fastdlserver URL
        m = re.search(r'id=([A-Za-z0-9+/=&]+)', fastdl_url)
        if m:
            fastdl_id = m.group(1)
            links.append({
                "quality": quality.strip(),
                "size": size.strip(),
                "fastdl_id": fastdl_id,
                "fastdl_url": fastdl_url.split('&amp;')[0]
            })
    
    # Also try linksmod pattern
    linksmod_pattern = r'<h5[^>]*>.*?(\d{3,4}p).*?\[(.*?)\].*?</h5>.*?href=["\']([^"\']*linksmod[^"\']*)["\']'
    linksmod_matches = re.findall(linksmod_pattern, html, re.DOTALL | re.IGNORECASE)
    
    for quality, size, linksmod_url in linksmod_matches:
        m = re.search(r'view/([A-Za-z0-9]+)', linksmod_url)
        if m:
            linksmod_id = m.group(1)
            # Check if this quality already exists
            exists = any(l["quality"] == quality.strip() for l in links)
            if not exists:
                links.append({
                    "quality": quality.strip(),
                    "size": size.strip(),
                    "linksmod_id": linksmod_id,
                    "linksmod_url": linksmod_url
                })
    
    return links

async def scrape_post(url):
    global _stats
    
    try:
        html = await fetch_html(url)
        if not html:
            _stats["failed"] += 1
            return None
        
        title, year, language, quality, size, genre, imdb_rating, cast, storyline = extract_metadata(html)
        download_links = extract_download_links(html)
        
        if not title:
            _stats["failed"] += 1
            return None
        
        _stats["scraped"] += 1
        _stats["links"] += len(download_links)
        
        return {
            "url": url,
            "title": title,
            "year": year,
            "language": language,
            "quality": quality,
            "size": size,
            "genre": genre,
            "imdb_rating": imdb_rating,
            "cast": cast,
            "storyline": storyline,
            "download_links": download_links
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
    
    print(f"[BollyFlix Scraper] Starting at {datetime.now()}")
    
    await init_table()
    
    sitemap_urls = await get_sitemap_urls()
    if not sitemap_urls:
        print("[BollyFlix Scraper] Failed to fetch sitemap")
        _stats["running"] = False
        return
    
    print(f"[BollyFlix Scraper] Found {len(sitemap_urls)} URLs")
    
    scraped_urls = await get_scraped_urls()
    new_urls = [u for u in sitemap_urls if u not in scraped_urls]
    
    print(f"[BollyFlix Scraper] Already: {len(scraped_urls)}, New: {len(new_urls)}")
    
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
                    result["language"], result["quality"], result["size"],
                    result["genre"], result["imdb_rating"], result["cast"],
                    result["storyline"], result["download_links"]
                )
            await asyncio.sleep(0.5)
            return result
    
    batch_size = 20
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i+batch_size]
        tasks = [_scrape_one(url) for url in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful = sum(1 for r in results if r and not isinstance(r, Exception))
        print(f"[BollyFlix Scraper] Batch {i//batch_size + 1}: {successful}/{len(batch)}")
    
    _stats["running"] = False
    print(f"[BollyFlix Scraper] Done! {_stats['scraped']} scraped, {_stats['links']} links")

def get_stats():
    return _stats.copy()

async def search_pre_scraped(query):
    async with aiosqlite.connect(DB_PATH) as db:
        results = []
        search_term = f"%{query}%"
        async with db.execute(
            "SELECT * FROM bollyflix_posts WHERE title LIKE ? LIMIT 10",
            (search_term,)
        ) as cursor:
            async for row in cursor:
                results.append({
                    "url": row[0],
                    "title": row[1],
                    "year": row[2],
                    "language": row[3],
                    "quality": row[4],
                    "size": row[5],
                    "genre": row[6],
                    "imdb_rating": row[7],
                    "cast": row[8],
                    "storyline": row[9],
                    "download_links": json.loads(row[10]) if row[10] else []
                })
        return results

async def resolve_fastdlserver(fastdl_id):
    """Resolve fastdlserver ID to get GDFlix link."""
    import base64
    try:
        # Decode base64 ID
        decoded = base64.b64decode(fastdl_id).decode()
        # This usually contains the gdflix URL or token
        return decoded
    except:
        return None
