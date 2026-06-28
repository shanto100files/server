"""
4KHDHub Pre-Scraper
Extracts metadata + HubCloud/HubDrive links from 4KHDHub posts.
"""
import re
import asyncio
import aiosqlite
import json
import time
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache.db")

# 4KHDHub domains
HDHUB_DOMAINS = ["https://4khdhub.one", "https://4khdhub.com"]

_stats = {"scraped": 0, "links": 0, "failed": 0, "last_run": None, "running": False}

async def init_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS hdhub4k_posts (
                url TEXT PRIMARY KEY,
                title TEXT,
                year TEXT,
                imdb_rating TEXT,
                genre TEXT,
                stars TEXT,
                print_info TEXT,
                audios TEXT,
                seasons TEXT,
                download_links TEXT,
                last_scraped REAL
            )
        """)
        await db.commit()

async def get_scraped_urls():
    async with aiosqlite.connect(DB_PATH) as db:
        urls = set()
        async with db.execute("SELECT url FROM hdhub4k_posts") as cursor:
            async for row in cursor:
                urls.add(row[0])
        return urls

async def save_post(url, title, year, imdb_rating, genre, stars, print_info, audios, seasons, download_links):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO hdhub4k_posts 
            (url, title, year, imdb_rating, genre, stars, print_info, audios, seasons, download_links, last_scraped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (url, title, year, imdb_rating, genre, stars, print_info, audios, seasons,
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
    """Get post URLs from 4KHDHub sitemap."""
    urls = []
    
    for domain in HDHUB_DOMAINS:
        html = await fetch_html(f"{domain}/sitemap.xml")
        if html:
            found = re.findall(r'<loc>(.*?)</loc>', html)
            urls.extend([u for u in found if "4khdhub" in u])
    
    return list(set(urls))

def extract_metadata(html):
    """Extract metadata from 4KHDHub page."""
    title = ""
    year = ""
    imdb_rating = ""
    genre = ""
    stars = ""
    print_info = ""
    audios = ""
    seasons = ""
    
    # Title
    m = re.search(r'<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>(.*?)</h1>', html)
    if m:
        title = m.group(1).strip()
    else:
        m = re.search(r'<title>(.*?)</title>', html)
        if m:
            title = m.group(1).split('–')[0].strip()
    
    # Year
    m = re.search(r'(\d{4})', title)
    if m:
        year = m.group(1)
    
    # IMDb Rating
    m = re.search(r'imdb-score[^>]*>([\d.]+)', html)
    if m:
        imdb_rating = m.group(1)
    
    # Genre
    genre_matches = re.findall(r'href="/category/([^"]+)/"[^>]*>([^<]+)', html)
    genre_list = [g[1] for g in genre_matches if g[1] not in ['Series', '1080p', '2160p', 'Dual Language', 'WEB-DL']]
    genre = ", ".join(genre_list[:5])
    
    # Stars
    m = re.search(r'Stars:\s*</span>\s*<span[^>]*>(.*?)</span>', html)
    if m:
        stars = m.group(1).strip()
    
    # Print Info
    m = re.search(r'Print:\s*</span>\s*<span[^>]*>(.*?)</span>', html)
    if m:
        print_info = m.group(1).strip()
    
    # Audios
    m = re.search(r'Audios:\s*</span>\s*<span[^>]*>(.*?)</span>', html)
    if m:
        audios = m.group(1).strip()
    
    # Seasons
    m = re.search(r'Seasons:\s*</span>\s*<span[^>]*>(.*?)</span>', html)
    if m:
        seasons = m.group(1).strip()
    
    return title, year, imdb_rating, genre, stars, print_info, audios, seasons

def extract_download_links(html):
    """Extract HubCloud and HubDrive links from HTML."""
    links = []
    
    # Find all download sections
    # Pattern: quality info followed by HubCloud/HubDrive links
    
    # HubCloud links
    hubcloud_pattern = r'href="(https://hubcloud\.[^"]+/drive/[^"]+)"[^>]*>.*?Download HubCloud'
    hubcloud_matches = re.findall(hubcloud_pattern, html, re.DOTALL)
    
    for url in hubcloud_matches:
        # Try to get quality info from nearby content
        links.append({
            "type": "hubcloud",
            "url": url
        })
    
    # HubDrive links
    hubdrive_pattern = r'href="(https://hubdrive\.[^"]+/file/[^"]+)"[^>]*>.*?Download HubDrive'
    hubdrive_matches = re.findall(hubdrive_pattern, html, re.DOTALL)
    
    for url in hubdrive_matches:
        links.append({
            "type": "hubdrive",
            "url": url
        })
    
    # Also try simpler patterns
    if not links:
        # Find any hubcloud/hubdrive URLs
        all_urls = re.findall(r'https://(?:hubcloud|hubdrive)\.[^\s"\'<>]+', html)
        for url in all_urls:
            if url not in [l["url"] for l in links]:
                link_type = "hubcloud" if "hubcloud" in url else "hubdrive"
                links.append({
                    "type": link_type,
                    "url": url
                })
    
    return links

async def scrape_post(url):
    global _stats
    
    try:
        html = await fetch_html(url)
        if not html:
            _stats["failed"] += 1
            return None
        
        title, year, imdb_rating, genre, stars, print_info, audios, seasons = extract_metadata(html)
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
            "imdb_rating": imdb_rating,
            "genre": genre,
            "stars": stars,
            "print_info": print_info,
            "audios": audios,
            "seasons": seasons,
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
    
    print(f"[4KHDHub Scraper] Starting at {datetime.now()}")
    
    await init_table()
    
    sitemap_urls = await get_sitemap_urls()
    if not sitemap_urls:
        print("[4KHDHub Scraper] Failed to fetch sitemap")
        _stats["running"] = False
        return
    
    print(f"[4KHDHub Scraper] Found {len(sitemap_urls)} URLs")
    
    scraped_urls = await get_scraped_urls()
    new_urls = [u for u in sitemap_urls if u not in scraped_urls]
    
    print(f"[4KHDHub Scraper] Already: {len(scraped_urls)}, New: {len(new_urls)}")
    
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
                    result["imdb_rating"], result["genre"], result["stars"],
                    result["print_info"], result["audios"], result["seasons"],
                    result["download_links"]
                )
            await asyncio.sleep(0.5)
            return result
    
    batch_size = 20
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i+batch_size]
        tasks = [_scrape_one(url) for url in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful = sum(1 for r in results if r and not isinstance(r, Exception))
        print(f"[4KHDHub Scraper] Batch {i//batch_size + 1}: {successful}/{len(batch)}")
    
    _stats["running"] = False
    print(f"[4KHDHub Scraper] Done! {_stats['scraped']} scraped, {_stats['links']} links")

def get_stats():
    return _stats.copy()

async def search_pre_scraped(query):
    async with aiosqlite.connect(DB_PATH) as db:
        results = []
        search_term = f"%{query}%"
        async with db.execute(
            "SELECT * FROM hdhub4k_posts WHERE title LIKE ? LIMIT 10",
            (search_term,)
        ) as cursor:
            async for row in cursor:
                results.append({
                    "url": row[0],
                    "title": row[1],
                    "year": row[2],
                    "imdb_rating": row[3],
                    "genre": row[4],
                    "stars": row[5],
                    "print_info": row[6],
                    "audios": row[7],
                    "seasons": row[8],
                    "download_links": json.loads(row[9]) if row[9] else []
                })
        return results
