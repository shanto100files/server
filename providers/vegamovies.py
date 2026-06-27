import re, json, base64, time
from urllib.parse import unquote, quote_plus
from bs4 import BeautifulSoup
from client import async_cf_get, async_cf_post

VEGAMOVIES_DOMAINS = ["https://vegamovies4u.co.in", "https://vegamovies.navy", "https://vegamovies.mq", "https://vegamovies.market", "https://vegamovies.tel", "https://vegamovie.sl"]
DYNAMIC_URLS = "https://raw.githubusercontent.com/SaurabhKaperwan/Utils/refs/heads/main/urls.json"

_DOMAIN_CACHE = {"url": None, "time": 0}
_DOMAIN_CACHE_TTL = 3600


async def _fetch(url, timeout=12):
    return await async_cf_get(url, headers={"Referer": "https://vegamovies4u.co.in"}, timeout=timeout)


async def _get_domain():
    global _DOMAIN_CACHE
    if _DOMAIN_CACHE["url"] and (time.time() - _DOMAIN_CACHE["time"] < _DOMAIN_CACHE_TTL):
        return _DOMAIN_CACHE["url"]
    try:
        r = await async_cf_get(DYNAMIC_URLS, timeout=8)
        if r:
            data = json.loads(r)
            dynamic_domain = data.get("vegamovies", "")
            if dynamic_domain:
                _DOMAIN_CACHE["url"] = dynamic_domain
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


def _find_post_in_html(html, qw, year, base_domain):
    """Search HTML for a post matching the query. Returns post_url or None."""
    soup = BeautifulSoup(html, "html.parser")
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
        return href
    # Fallback: h3.entry-title > a
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
        return href
    # Fallback: any <a> with .html href
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
        return href
    return None


async def _search_typesense(domain, title):
    """Try Typesense JSON search on a domain. Returns list of (url, title) or empty."""
    try:
        html = await async_cf_get(f"{domain}/search.php?q={quote_plus(title)}&page=1", timeout=10)
        if not html:
            return []
        data = json.loads(html)
        hits = data.get("hits", [])
        results = []
        for hit in hits:
            doc = hit.get("document", {})
            permalink = doc.get("permalink", "")
            post_title = doc.get("post_title", "")
            if permalink and post_title:
                url = permalink if permalink.startswith("http") else domain + permalink
                results.append((url, post_title))
        return results
    except:
        return []


async def _search_dle(domain, title, timeout=10):
    """Try DLE CMS search (POST then GET). Returns HTML string or None."""
    body = f"do=search&subaction=search&story={quote_plus(title)}"
    resp = await async_cf_post(domain + "/", data=body, headers={
        "Referer": domain + "/",
        "Content-Type": "application/x-www-form-urlencoded",
    }, timeout=timeout)
    if resp:
        text = resp.text if hasattr(resp, 'text') else resp
        if text and len(text) > 2000 and ("post-item" in text or "entry-title" in text):
            return text
    html = await async_cf_get(f"{domain}/?do=search&subaction=search&story={quote_plus(title)}", timeout=timeout)
    if html and len(html) > 2000 and ("post-item" in html or "entry-title" in html):
        return html
    return None


def _match_title(title_text, qw, year):
    """Check if a title matches the query words. Returns True if good match."""
    pt_lower = title_text.lower().replace("download", "").strip()
    tw = set(pt_lower.split())
    overlap = qw & tw
    if not overlap:
        return False
    precision = len(overlap) / len(qw) if qw else 0
    if precision < 0.5:
        return False
    if len(qw) == 1:
        query_word = list(qw)[0]
        if not pt_lower.startswith(query_word):
            return False
    if year and year not in title_text:
        return False
    return True


async def vegamovies(title, tmdb_id="", season=0, episode=0, year="", media_type=""):
    domain = await _get_domain()
    qw = set(title.lower().split())
    post_url = None
    base_domain = domain

    # Strategy 1: Typesense on primary domain (vegamovies.navy)
    ts_hits = await _search_typesense(domain, title)
    for url, post_title in ts_hits:
        if _match_title(post_title, qw, year):
            post_url = url
            base_domain = domain
            break

    # Strategy 2: Typesense on vegamovies4u.co.in (if primary didn't work)
    if not post_url:
        dle_domain = "https://vegamovies4u.co.in"
        ts_hits2 = await _search_typesense(dle_domain, title)
        for url, post_title in ts_hits2:
            if _match_title(post_title, qw, year):
                post_url = url
                base_domain = dle_domain
                break

    # Strategy 3: DLE search on vegamovies4u.co.in
    if not post_url:
        dle_html = await _search_dle("https://vegamovies4u.co.in", title, timeout=12)
        if dle_html:
            post_url = _find_post_in_html(dle_html, qw, year, "https://vegamovies4u.co.in")
            if post_url:
                base_domain = "https://vegamovies4u.co.in"

    # Strategy 4: DLE search on primary domain (if it's different from vegamovies4u.co.in)
    if not post_url and domain != "https://vegamovies4u.co.in":
        dle_html2 = await _search_dle(domain, title, timeout=12)
        if dle_html2:
            post_url = _find_post_in_html(dle_html2, qw, year, domain)
            if post_url:
                base_domain = domain

    if not post_url:
        return []

    # Fetch post page and extract download links
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
        if not any(x in h for x in ["nexdrive", "vgmlinks", "hubcloud", "vcloud"]):
            continue
        nex_html = await _fetch(h, timeout=10)
        if not nex_html:
            continue
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
