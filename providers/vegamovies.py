import re, json, base64, time
import asyncio
from urllib.parse import unquote
from bs4 import BeautifulSoup
from client import async_cf_get, async_cf_post

VEGAMOVIES_DOMAINS = ["https://vegamovies4u.co.in", "https://vegamovies.navy", "https://vegamovies.mq", "https://vegamovies.market", "https://vegamovies.tel", "https://vegamovie.sl"]
DYNAMIC_URLS = "https://raw.githubusercontent.com/SaurabhKaperwan/Utils/refs/heads/main/urls.json"

_DOMAIN_CACHE = {"url": None, "time": 0}
_DOMAIN_CACHE_TTL = 3600  # 1 hour


async def _fetch(url, timeout=12):
    return await async_cf_get(url, headers={"Referer": "https://vegamovies4u.co.in"}, timeout=timeout)

async def _dle_search(domain, query, timeout=12):
    """VegaMovies search — handle both Typesense (WordPress) and DLE CMS sites"""
    from urllib.parse import quote_plus
    qw = set(query.lower().split())
    
    def _has_query_in_html(html, qw):
        soup = BeautifulSoup(html, "html.parser")
        for article in soup.find_all("article", class_=re.compile(r"post-item", re.I)):
            a_tag = article.find("a", href=True)
            if not a_tag:
                continue
            title = a_tag.get("title", "") or a_tag.get_text(strip=True)
            if not title:
                h3 = article.find("h3")
                if h3:
                    title = h3.get_text(strip=True)
            if not title:
                img = a_tag.find("img")
                if img:
                    title = img.get("alt", "")
            if title:
                tw = set(title.lower().split())
                if qw & tw:
                    return True
        return False

    # Try Typesense JSON API first (vegamovies.navy / WordPress sites)
    html = await async_cf_get(f"{domain}/search.php?q={quote_plus(query)}&page=1", timeout=timeout)
    if html:
        try:
            data = json.loads(html)
            hits = data.get("hits", [])
            if hits:
                return {"type": "typesense", "data": data, "domain": domain}
        except (json.JSONDecodeError, KeyError):
            pass
    
    # Try DLE CMS POST search first (most DLE sites require POST for search)
    body = f"do=search&subaction=search&story={quote_plus(query)}"
    resp = await async_cf_post(domain + "/", data=body, headers={
        "Referer": domain + "/",
        "Content-Type": "application/x-www-form-urlencoded",
    }, timeout=timeout)
    if resp:
        text = resp.text if hasattr(resp, 'text') else resp
        if text and len(text) > 2000 and ("post-item" in text or "entry-title" in text):
            if _has_query_in_html(text, qw):
                return {"type": "dle", "data": text, "domain": domain}

    # Try DLE CMS GET search
    html2 = await async_cf_get(f"{domain}/?do=search&subaction=search&story={quote_plus(query)}", timeout=timeout)
    if html2 and ("post-item" in html2 or "entry-title" in html2):
        if _has_query_in_html(html2, qw):
            return {"type": "dle", "data": html2, "domain": domain}

    # Try index.php GET
    html3 = await async_cf_get(f"{domain}/index.php?do=search&subaction=search&story={quote_plus(query)}", timeout=timeout)
    if html3 and ("post-item" in html3 or "entry-title" in html3):
        if _has_query_in_html(html3, qw):
            return {"type": "dle", "data": html3, "domain": domain}
    
    return None

async def _get_domain():
    global _DOMAIN_CACHE
    if _DOMAIN_CACHE["url"] and (time.time() - _DOMAIN_CACHE["time"] < _DOMAIN_CACHE_TTL):
        return _DOMAIN_CACHE["url"]
    
    # Dynamic URL may return vegamovies.navy (WordPress/Typesense, limited content)
    # or vegamovies4u.co.in (DLE CMS, more content). Prefer DLE site.
    try:
        r = await async_cf_get(DYNAMIC_URLS, timeout=8)
        if r:
            data = json.loads(r)
            dynamic_domain = data.get("vegamovies", "")
            # If dynamic gives us a DLE site, use it; otherwise use the DLE domain
            if "4u" in dynamic_domain or "co.in" in dynamic_domain:
                _DOMAIN_CACHE["url"] = dynamic_domain
            else:
                _DOMAIN_CACHE["url"] = VEGAMOVIES_DOMAINS[0]
            _DOMAIN_CACHE["time"] = time.time()
            return _DOMAIN_CACHE["url"]
    except:
        pass
        
    if _DOMAIN_CACHE["url"]:
        return _DOMAIN_CACHE["url"]
    return VEGAMOVIES_DOMAINS[0]

async def _resolve_vcloud(url):
    html = await _fetch(url, timeout=10)
    if not html:
        return []
    m = re.search(r'var\s+url\s*=\s*atob\(atob\(["\']([^"\']+)["\']\)\)', html)
    if not m:
        return []
    b64 = m.group(1)
    while len(b64) % 4 != 0:
        b64 += "="
    try:
        once = base64.b64decode(b64).decode()
        while len(once) % 4 != 0:
            once += "="
        token_url = base64.b64decode(once).decode()
    except:
        return []
    token_html = await _fetch(token_url, timeout=10)
    if not token_html:
        return []
    results = []
    soup = BeautifulSoup(token_html, "html.parser")
    for h2 in soup.find_all("h2"):
        for a in h2.find_all_next("a", href=True):
            h = a["href"]
            t = a.get_text(strip=True)
            if not h.startswith("http"):
                continue
            if any(x in h for x in [".css", ".js", "fonts", "favicon"]):
                continue
            quality = "HD"
            combined = t + " " + unquote(h)
            for q in ["2160p", "4K", "1080p", "720p", "480p"]:
                if q.lower() in combined.lower():
                    quality = q
                    break
            if "FSLv2" in t or "FSL" in t or "10Gbps" in t or "Mega" in t or "Buzz" in t or "Pixeldrain" in t:
                results.append({"url": h, "quality": quality})
                if len(results) >= 6:
                    break
        if results:
            break
    return results

async def vegamovies(title, tmdb_id="", season=0, episode=0, year="", media_type=""):
    import traceback
    try:
        return await _vegamovies_inner(title, tmdb_id, season, episode, year, media_type)
    except Exception as e:
        print(f"[VegaMovies] ERROR: {e}")
        traceback.print_exc()
        return []

async def _vegamovies_inner(title, tmdb_id="", season=0, episode=0, year="", media_type=""):
    domain = await _get_domain()
    search_result = await _dle_search(domain, title, timeout=12)
    if not search_result:
        return []
    
    post_url = None
    search_type = search_result["type"]
    search_data = search_result["data"]
    base_domain = search_result["domain"]
    
    if search_type == "typesense":
        hits = search_data.get("hits", [])
        qw = set(title.lower().split())
        for hit in hits:
            doc = hit.get("document", {})
            permalink = doc.get("permalink", "")
            post_title = doc.get("post_title", "")
            if not permalink:
                continue
            pt_lower = post_title.lower()
            tw = set(pt_lower.split())
            overlap = qw & tw
            if not overlap:
                continue
            precision = len(overlap) / len(qw) if qw else 0
            if precision < 0.5:
                continue
            if year and year not in post_title:
                continue
            post_url = permalink if permalink.startswith("http") else base_domain + permalink
            break
    elif search_type == "dle":
        soup = BeautifulSoup(search_data, "html.parser")
        qw = set(title.lower().split())
        # Try article.post-item first
        for article in soup.find_all("article", class_=re.compile(r"post-item", re.I)):
            a_tag = article.find("a", href=True)
            if not a_tag:
                continue
            href = a_tag["href"]
            post_title = a_tag.get("title", "") or a_tag.get_text(strip=True)
            if not post_title:
                h3 = article.find("h3")
                if h3:
                    post_title = h3.get_text(strip=True)
            if not post_title:
                img = a_tag.find("img")
                if img:
                    post_title = img.get("alt", "")
            if not href.startswith("http"):
                href = base_domain + href
            pt_lower = post_title.lower()
            tw = set(pt_lower.split())
            overlap = qw & tw
            if not overlap:
                continue
            precision = len(overlap) / len(qw) if qw else 0
            if precision < 0.5:
                continue
            if year and year not in post_title:
                continue
            post_url = href
            break
        # Fallback: try h3.entry-title > a
        if not post_url:
            for h3 in soup.find_all("h3", class_=re.compile(r"entry-title|post-title", re.I)):
                a_tag = h3.find("a", href=True)
                if not a_tag:
                    continue
                href = a_tag["href"]
                post_title = a_tag.get("title", "") or a_tag.get_text(strip=True)
                if not href.startswith("http"):
                    href = base_domain + href
                pt_lower = post_title.lower()
                tw = set(pt_lower.split())
                overlap = qw & tw
                if not overlap:
                    continue
                precision = len(overlap) / len(qw) if qw else 0
                if precision < 0.5:
                    continue
                if year and year not in post_title:
                    continue
                post_url = href
                break
        # Fallback: try any <a> with href ending in .html
        if not post_url:
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                post_title = a_tag.get("title", "") or a_tag.get_text(strip=True)
                if not post_title:
                    img = a_tag.find("img")
                    if img:
                        post_title = img.get("alt", "")
                if not href.endswith(".html"):
                    continue
                if not href.startswith("http"):
                    href = base_domain + href
                pt_lower = post_title.lower()
                tw = set(pt_lower.split())
                overlap = qw & tw
                if not overlap:
                    continue
                precision = len(overlap) / len(qw) if qw else 0
                if precision < 0.5:
                    continue
                if year and year not in post_title:
                    continue
                post_url = href
                break
    
    if not post_url:
        return []
    post_html = await _fetch(post_url, timeout=12)
    if not post_html:
        return []
    soup = BeautifulSoup(post_html, "html.parser")
    final = []
    seen = set()
    for a in soup.find_all("a", href=True):
        h = a["href"]
        t = a.get_text(strip=True)
        if not h or "#" in h or not h.startswith("http"):
            continue
        # Direct download links (fast-dl.one)
        if "fast-dl.one" in h:
            if h in seen:
                continue
            seen.add(h)
            combined = t + " " + unquote(h)
            quality = "HD"
            for q in ["2160p", "4K", "1080p", "720p", "480p"]:
                if q.lower() in combined.lower():
                    quality = q
                    break
            # Try to detect quality from link text
            if quality == "HD" and t:
                tl = t.lower()
                if "1080" in tl:
                    quality = "1080p"
                elif "720" in tl:
                    quality = "720p"
                elif "480" in tl:
                    quality = "480p"
                elif "2160" in tl or "4k" in tl:
                    quality = "4K"
            fmt = "mkv" if ".mkv" in h else "mp4"
            final.append({"url": h, "quality": quality, "provider": "VegaMovies", "format": fmt})
            continue
        # Link protector pages (vgmlinks, nexdrive, hubcloud, etc.)
        if not any(x in h for x in ["nexdrive", "vgmlinks", "hubcloud", "vcloud"]):
            continue
        nex_html = await _fetch(h, timeout=10)
        if not nex_html:
            continue
        # Try to find fast-dl.one link in protector page
        fast_match = re.search(r'href="(https?://fast-dl\.one/dl/[^"]+)"', nex_html)
        if fast_match:
            dl_url = fast_match.group(1)
            if dl_url in seen:
                continue
            seen.add(dl_url)
            combined = t + " " + unquote(dl_url)
            quality = "HD"
            for q in ["2160p", "4K", "1080p", "720p", "480p"]:
                if q.lower() in combined.lower():
                    quality = q
                    break
            fmt = "mkv" if ".mkv" in dl_url else "mp4"
            final.append({"url": dl_url, "quality": quality, "provider": "VegaMovies", "format": fmt})
            continue
        # Fallback: try vcloud/hubcloud resolution
        vcloud_url = None
        for m in re.finditer(r'href="(https?://vcloud\.zip/[^"]*)"', nex_html):
            vcloud_url = m.group(1)
            break
        if not vcloud_url:
            for m in re.finditer(r'href="(https?://[^"]*(?:hubcloud|vcloud)[^"]*)"', nex_html):
                hh = m.group(1)
                if "signup" not in hh and "tg/" not in hh and "bit.ly" not in hh:
                    vcloud_url = hh
                    break
        if not vcloud_url:
            continue
        resolved = await _resolve_vcloud(vcloud_url)
        for r in resolved:
            url = r["url"]
            if url in seen:
                continue
            seen.add(url)
            quality = r.get("quality", "HD")
            for q in ["2160p", "4K", "1080p", "720p", "480p"]:
                if q.lower() in url.lower():
                    quality = q
                    break
            fmt = "mkv" if ".mkv" in url else "mp4"
            final.append({"url": url, "quality": quality, "provider": "VegaMovies", "format": fmt})
    return final[:10]
