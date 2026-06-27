import re
import base64
import asyncio
from urllib.parse import quote as urlquote
from bs4 import BeautifulSoup
from client import async_cf_get
from providers.gdflix import resolve_gdflix
from providers.auto_resolver import resolve_any

CINEFREAK_DOMAINS = ["https://cinefreak.net", "https://cinefreak.nl", "https://cinefreak.site"]
CINECLOUD_BASE = "https://new5.cinecloud.site"

async def _get_domain() -> str:
    for domain in CINEFREAK_DOMAINS:
        r = await async_cf_get(domain, timeout=5)
        if r:
            return domain
    return CINEFREAK_DOMAINS[0]

async def _fetch(url: str, headers: dict = None) -> str | None:
    r = await async_cf_get(url, headers=headers or {}, timeout=15)
    if r:
        return r
    return None

def _parse_filename_meta(filename: str) -> dict:
    meta = {}
    season_match = re.search(r'S(\d+)E', filename, re.IGNORECASE)
    if season_match:
        meta["season"] = int(season_match.group(1))
    ep_match = re.search(r'S\d+E(\d+)(?:-E?(\d+))?', filename, re.IGNORECASE)
    if ep_match:
        start = int(ep_match.group(1))
        end = int(ep_match.group(2)) if ep_match.group(2) else start
        meta["episode_label"] = f"E{start}" if start == end else f"E{start}-E{end}"
        meta["ep_start"] = start
        meta["ep_end"] = end
    q_match = re.search(r'(2160p|1080p|720p|480p|4K)', filename, re.IGNORECASE)
    if q_match:
        meta["quality"] = q_match.group(1)
    for lang in ["Bengali", "Bengal", "Hindi", "Tamil", "Telugu", "English", "Kannada", "Malayalam", "Punjabi", "Marathi"]:
        if lang.lower() in filename.lower():
            meta["language"] = "Bengali" if lang == "Bengal" else lang
            break
    if filename.endswith(".mkv"):
        meta["format"] = "mkv"
    elif filename.endswith(".mp4"):
        meta["format"] = "mp4"
    return meta

async def _extract_direct_links(html: str) -> list[str]:
    results = []
    soup = BeautifulSoup(html, "html.parser")
    loop = asyncio.get_event_loop()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if not href:
            continue
        full = href if href.startswith("http") else f"{CINECLOUD_BASE}{href}"
        if any(x in full for x in ["r2.dev", "r2.cloudflarestorage.com", "pixeldrain", "googleusercontent.com", "filepress"]):
            if full not in results:
                results.append(full)
        elif "gdflix" in full:
            gdflix_resolved = await loop.run_in_executor(None, lambda: resolve_gdflix(full))
            for g in gdflix_resolved:
                u = g.get("url", "")
                if u and u not in results:
                    results.append(u)
    return results

async def _resolve_cinecloud(page_url: str, _depth: int = 0) -> tuple[list[str], dict]:
    if _depth > 2:
        return [], {}
    # Add small delay between retries to avoid rate limiting
    if _depth > 0:
        await asyncio.sleep(0.3 * _depth)

    html = await _fetch(page_url, {"Referer": "https://new5.cinecloud.site", "Cookie": "xla=s4t"})
    if not html or len(html) < 500:
        return [], {}

    soup = BeautifulSoup(html, "html.parser")
    meta = {}
    title_el = soup.select_one("h1.file-title, .card-header")
    if title_el:
        fname = title_el.get_text(strip=True)
        meta["filename"] = fname
        meta = _parse_filename_meta(fname)
        meta["filename"] = fname
    size_el = soup.select_one("td.text-right")
    if size_el:
        prev = size_el.find_previous_sibling("td")
        if prev and "size" in prev.get_text(strip=True).lower():
            meta["fileSize"] = size_el.get_text(strip=True)

    links = await _extract_direct_links(html)
    if links:
        return links, meta

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        full = href if href.startswith("http") else f"{CINECLOUD_BASE}{href}"

        if "/d/" in href:
            dl_html = await _fetch(full, {"Referer": "https://new5.cinecloud.site", "Cookie": "xla=s4t"})
            if dl_html:
                dl_links = await _extract_direct_links(dl_html)
                if dl_links:
                    return dl_links, meta

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        full = href if href.startswith("http") else f"{CINECLOUD_BASE}{href}"

        if "/w/" in href or "/gp/" in href:
            inner_html = await _fetch(full, {"Referer": "https://new5.cinecloud.site", "Cookie": "xla=s4t"})
            if inner_html:
                inner_links = await _extract_direct_links(inner_html)
                if inner_links:
                    return inner_links, meta

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        full = href if href.startswith("http") else f"{CINECLOUD_BASE}{href}"
        if "/f/" in href and full != page_url:
            return await _resolve_cinecloud(full, _depth + 1)

    loop = asyncio.get_event_loop()
    resolved = await loop.run_in_executor(None, lambda: resolve_any(page_url, referer=CINECLOUD_BASE))
    if resolved:
        return [r["url"] for r in resolved], meta

    return [], meta

def _parse_episode_range(text: str) -> tuple[int, int]:
    """Parse 'Episode 1-3' or 'Episode 5' → (start, end)"""
    m = re.search(r'Episode\s*(\d+)\s*[-–]\s*(\d+)', text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.search(r'Episode\s*(\d+)', text)
    if m:
        n = int(m.group(1))
        return (n, n)
    return (0, 0)

def _get_card_episode_range(card) -> tuple[int, int]:
    """Get episode range from ep-card element"""
    card_text = card.get_text(" ", strip=True)
    start, end = _parse_episode_range(card_text)
    if start > 0:
        return (start, end)
    e_el = card.select_one("span.episode-badge")
    if e_el:
        e_text = e_el.get_text(strip=True)
        start, end = _parse_episode_range(e_text)
        if start > 0:
            return (start, end)
    for el in card.select("span, div, p"):
        t = el.get_text(strip=True)
        s, e = _parse_episode_range(t)
        if s > 0:
            return (s, e)
    return (0, 0)

async def cinefreak(tmdb_id: str, media_type: str, title: str, season: int = 0, episode: int = 0) -> list[dict]:
    sources = []
    domain = await _get_domain()
    query = f"{title} Season {season}" if media_type == "tv" and season > 0 else title

    search_html = await _fetch(
        f"{domain}/search-api.php?q={urlquote(query)}&pg=1"
    )
    if not search_html:
        return sources

    try:
        import json
        data = json.loads(search_html)
        results = data.get("results", [])
        if not results:
            return sources
    except:
        return sources

    best = results[0]
    if season > 0:
        for r in results:
            t = (r.get("t", "") + " " + r.get("l", "")).lower()
            if f"season {season}" in t or f"s{season}" in t:
                best = r
                break

    post_path = best.get("l") or best.get("url", "")
    if not post_path.startswith("http"):
        post_path = f"{domain}/{post_path}/"

    post_html = await _fetch(post_path, {"Cookie": "xla=s4t"})
    if not post_html:
        return sources

    soup = BeautifulSoup(post_html, "html.parser")

    # Collect all resolve tasks first, then run them in parallel
    resolve_tasks = []

    if media_type == "tv":
        dl_div = soup.select_one("div.download-links-div")
        if dl_div:
            current_title = ""
            for child in dl_div.children:
                if not hasattr(child, 'name') or not child.name:
                    continue
                if child.name == 'h4' and 'movie-title' in (child.get('class') or []):
                    current_title = child.get_text(strip=True)
                elif child.name == 'div' and 'dlbtn-container' in (child.get('class') or []):
                    ep_start, ep_end = _parse_episode_range(current_title)
                    ep_label = f"E{ep_start}" if ep_start == ep_end else f"E{ep_start}-E{ep_end}" if ep_start > 0 else ""
                    quality = _extract_quality(current_title)

                    for a in child.select("a[href*='generate.php']"):
                        href = a.get("href", "")
                        gen_url = href if href.startswith("http") else f"{domain}{href}"
                        m_id = re.search(r'id=([A-Za-z0-9+/=]+)', gen_url)
                        if m_id:
                            try:
                                decoded = base64.b64decode(m_id.group(1)).decode()
                                decoded = re.sub(r'newgo\d+$', '', decoded)
                                decoded = decoded.replace("/x/", "/f/")
                                resolve_tasks.append((decoded, quality, ep_label, ep_start, ep_end))
                            except:
                                pass

        if not resolve_tasks:
            for link in soup.select("a[href*='generate.php'], a[href*='cinecloud'], a[href*='/x/'], a[href*='/f/']")[:10]:
                href = link.get("href", "")
                quality = _extract_quality(link.text)
                if "generate.php" in href:
                    gen_url = href if href.startswith("http") else f"{domain}{href}"
                    m_id = re.search(r'id=([A-Za-z0-9+/=]+)', gen_url)
                    if m_id:
                        try:
                            decoded = base64.b64decode(m_id.group(1)).decode()
                            decoded = re.sub(r'newgo\d+$', '', decoded)
                            decoded = decoded.replace("/x/", "/f/")
                            resolve_tasks.append((decoded, quality, "", 0, 0))
                        except:
                            pass
                elif "/f/" in href or "/x/" in href or "cinecloud" in href:
                    cinecloud_url = href if href.startswith("http") else f"{CINECLOUD_BASE}{href}"
                    cinecloud_url = cinecloud_url.replace("/x/", "/f/")
                    resolve_tasks.append((cinecloud_url, quality, "", 0, 0))
    else:
        for link in soup.select("a[href*='generate.php'], a[href*='cinecloud'], a[href*='/x/'], a[href*='/f/'], a[href*='neodrive'], a[href*='hubcloud']")[:10]:
            href = link.get("href", "")
            quality = _extract_quality(link.text)
            if "/f/" in href or "/x/" in href or "cinecloud" in href:
                cinecloud_url = href if href.startswith("http") else f"{CINECLOUD_BASE}{href}"
                cinecloud_url = cinecloud_url.replace("/x/", "/f/")
                resolve_tasks.append((cinecloud_url, quality, "", 0, 0))
            elif "generate.php" in href:
                gen_url = href if href.startswith("http") else f"{domain}{href}"
                m_id = re.search(r'id=([A-Za-z0-9+/=]+)', gen_url)
                if m_id:
                    try:
                        decoded = base64.b64decode(m_id.group(1)).decode()
                        decoded = re.sub(r'newgo\d+$', '', decoded)
                        decoded = decoded.replace("/x/", "/f/")
                        resolve_tasks.append((decoded, quality, "", 0, 0))
                    except:
                        pass
            else:
                sources.append({"url": href, "quality": quality, "provider": "CineFreak"})

    # Parallel resolve with concurrency limit
    async def _resolve_one(task):
        url, quality, ep_label, ep_start, ep_end = task
        try:
            dl_links, cc_meta = await _resolve_cinecloud(url)
            result_sources = []
            for dl in dl_links:
                s = {"url": dl, "quality": cc_meta.get("quality", quality), "provider": "CineFreak", "format": cc_meta.get("format", "mp4"), "episode_label": cc_meta.get("episode_label", ep_label)}
                if cc_meta.get("season"): s["season"] = cc_meta["season"]
                if ep_start > 0:
                    s["ep_start"] = ep_start
                    s["ep_end"] = ep_end if ep_end > 0 else ep_start
                elif cc_meta.get("ep_start"):
                    s["ep_start"] = cc_meta["ep_start"]
                    s["ep_end"] = cc_meta.get("ep_end", cc_meta["ep_start"])
                if cc_meta.get("fileSize"): s["fileSize"] = cc_meta["fileSize"]
                if cc_meta.get("language"): s["language"] = cc_meta["language"]
                if cc_meta.get("filename"): s["filename"] = cc_meta["filename"]
                result_sources.append(s)
            # Also add intermediate link for indexing (if different from resolved)
            if dl_links and url not in dl_links:
                intermediate = {"url": url, "quality": quality, "provider": "CineFreak", "format": "mp4", "episode_label": ep_label, "_intermediate": True}
                result_sources.append(intermediate)
            if not dl_links:
                result_sources.append({"url": url, "quality": quality, "provider": "CineFreak", "format": "mp4", "episode_label": ep_label})
            return result_sources
        except:
            return [{"url": url, "quality": quality, "provider": "CineFreak", "format": "mp4"}]

    if resolve_tasks:
        # Limit to 8 concurrent resolutions to avoid overwhelming
        sem = asyncio.Semaphore(8)
        async def _limited_resolve(task):
            async with sem:
                return await _resolve_one(task)
        results = await asyncio.gather(*[_limited_resolve(t) for t in resolve_tasks], return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                sources.extend(r)

    return sources

def _extract_quality(text: str) -> str:
    m = re.search(r"(1080p|720p|480p|4K|2160p)", text, re.IGNORECASE)
    return m.group(1) if m else "HD"
