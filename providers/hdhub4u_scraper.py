"""
HDHub4U Pre-Scraper
Scrapes hdhub4u posts and stores download links to SQLite.
"""
import re
import asyncio
import aiosqlite
import json
import time
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache.db")

_stats = {"scraped": 0, "links": 0, "failed": 0, "last_run": None, "running": False}

async def init_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS hdhub4u_posts (
                url TEXT PRIMARY KEY,
                title TEXT,
                year TEXT,
                language TEXT,
                quality TEXT,
                download_links TEXT,
                last_scraped REAL
            )
        """)
        await db.commit()

async def get_scraped_urls():
    async with aiosqlite.connect(DB_PATH) as db:
        urls = set()
        async with db.execute("SELECT url FROM hdhub4u_posts") as cursor:
            async for row in cursor:
                urls.add(row[0])
        return urls

async def save_post(url, title, year, language, quality, download_links):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO hdhub4u_posts 
            (url, title, year, language, quality, download_links, last_scraped)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (url, title, year, language, quality, json.dumps(download_links), time.time()))
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
    """Get post URLs from HDHub4U sitemap."""
    urls = []
    
    # Try multiple sitemap URLs
    sitemap_urls_to_try = [
        "https://hdhub4u.website/custom-sitemap.php",
        "https://new2.hdhub4u.cl/post-sitemap.xml",
        "https://hdhub4u.website/sitemap.xml",
    ]
    
    for sm_url in sitemap_urls_to_try:
        html = await fetch_html(sm_url)
        if html:
            # Find post URLs
            found = re.findall(r'<loc>(.*?)</loc>', html)
            urls.extend([u for u in found if "hdhub4u" in u])
            
            # Also try line-by-line URLs
            lines = html.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('http') and 'hdhub4u' in line:
                    if line not in urls:
                        urls.append(line)
    
    return list(set(urls))

def extract_metadata(html):
    title = ""
    year = ""
    language = ""
    quality = ""
    
    m = re.search(r'<title>(.*?)</title>', html)
    if m:
        title = m.group(1).split('–')[0].strip()
    
    m = re.search(r'(\d{4})', title)
    if m:
        year = m.group(1)
    
    for lang in ["Hindi", "English", "Bengali", "Tamil", "Telugu", "Dual Audio"]:
        if lang.lower() in title.lower():
            language = lang
            break
    
    m = re.search(r'(480p|720p|1080p|2160p|4K)', title)
    if m:
        quality = m.group(1)
    
    return title, year, language, quality

def extract_download_links(html):
    """Extract download links from HDHub4U page."""
    links = []
    
    # Find various download link patterns
    patterns = [
        r'href=["\']([^"\']*(?:drive\.google|mega\.nz|terabox|gofile|mediafire)[^"\']*)["\']',
        r'href=["\']([^"\']*(?:download|dl)[^"\']*)["\']',
        r'https?://[^\s"\'<>]+(?:drive\.google|mega\.nz|terabox|gofile)[^\s"\'<>]*',
    ]
    
    for pattern in patterns:
        found = re.findall(pattern, html, re.IGNORECASE)
        for url in found:
            if url and url.startswith('http') and url not in links:
                links.append(url)
    
    return links

async def scrape_post(url):
    global _stats
    
    try:
        html = await fetch_html(url)
        if not html:
            _stats["failed"] += 1
            return None
        
        title, year, language, quality = extract_metadata(html)
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
    
    print(f"[HDHub4U Scraper] Starting at {datetime.now()}")
    
    await init_table()
    
    sitemap_urls = await get_sitemap_urls()
    if not sitemap_urls:
        print("[HDHub4U Scraper] Failed to fetch sitemap")
        _stats["running"] = False
        return
    
    print(f"[HDHub4U Scraper] Found {len(sitemap_urls)} URLs")
    
    scraped_urls = await get_scraped_urls()
    new_urls = [u for u in sitemap_urls if u not in scraped_urls]
    
    print(f"[HDHub4U Scraper] Already: {len(scraped_urls)}, New: {len(new_urls)}")
    
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
                    result["language"], result["quality"], result["download_links"]
                )
            await asyncio.sleep(0.5)
            return result
    
    batch_size = 20
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i+batch_size]
        tasks = [_scrape_one(url) for url in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful = sum(1 for r in results if r and not isinstance(r, Exception))
        print(f"[HDHub4U Scraper] Batch {i//batch_size + 1}: {successful}/{len(batch)}")
    
    _stats["running"] = False
    print(f"[HDHub4U Scraper] Done! {_stats['scraped']} scraped, {_stats['links']} links")

def get_stats():
    return _stats.copy()

async def search_pre_scraped(query):
    async with aiosqlite.connect(DB_PATH) as db:
        results = []
        search_term = f"%{query}%"
        async with db.execute(
            "SELECT * FROM hdhub4u_posts WHERE title LIKE ? LIMIT 10",
            (search_term,)
        ) as cursor:
            async for row in cursor:
                results.append({
                    "url": row[0],
                    "title": row[1],
                    "year": row[2],
                    "language": row[3],
                    "quality": row[4],
                    "download_links": json.loads(row[5]) if row[5] else []
                })
        return results
