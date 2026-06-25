import re
from bs4 import BeautifulSoup
from client import cf_get
from providers.gdflix import resolve_gdflix, _is_streamable
from providers.auto_resolver import resolve_any, is_direct_streamable, content_matches, title_matches_search, score_content

MLSBD_DOMAINS = ["https://mlsbd.co", "https://mlsbd.net", "https://mlsbd.com"]

def _fetch(url, headers=None):
    return cf_get(url, headers=headers, timeout=15)

def _resolve_savelinks(url):
    html = _fetch(url, headers={"Referer": "https://mlsbd.co"})
    if not html:
        return []
    from urllib.parse import urlparse
    links = re.findall(r'href="(https?://[^"]*)"', html)
    js_links = re.findall(r'"(https?://[^"]*(?:filepress|gdflix)[^"]*)"', html)
    skip_hosts = {"mlsbd.co", "mlsbd.net", "mlsbd.com", "t.me", "telegram.me", "telegram.dog"}
    seen, result = set(), []
    base_host = urlparse(url).hostname or "savelinks.me"
    for link in list(set(links + js_links)):
        host = urlparse(link).hostname or ""
        if host != base_host and host not in seen and host not in skip_hosts:
            seen.add(host)
            result.append(link)
    return result

def _extract_post_metadata(html: str) -> dict:
    meta = {}
    text = BeautifulSoup(html, "lxml").get_text()
    lang = re.search(r"Language\s*:\s*(\w+)", text)
    if lang:
        meta["language"] = lang.group(1)
    qual = re.search(r"Quality\s*:\s*(\w+)", text)
    if qual:
        meta["quality_tag"] = qual.group(1)
    size = re.search(r"Size\s*:\s*([^\n]+)", text)
    if size:
        meta["sizes"] = [s.strip() for s in size.group(1).split("|")]
    res = re.search(r"Resolution\s*:\s*([^\n]+)", text)
    if res:
        meta["resolutions"] = [r.strip().lower() for r in res.group(1).split("|")]
    return meta

def _match_size_to_quality(quality: str, meta: dict) -> str:
    sizes = meta.get("sizes", [])
    resolutions = meta.get("resolutions", [])
    if not sizes:
        return ""
    q = quality.lower().replace("p", "")
    for i, res in enumerate(resolutions):
        if q in res.replace("p", "") and i < len(sizes):
            return sizes[i]
    if len(sizes) == 1:
        return sizes[0]
    return ""

def _parse_episode_from_text(text: str) -> str:
    m = re.search(r'(?:Epi-?|Ep(?:isode)?\.?\s*|E)\s*(\d+)', text, re.IGNORECASE)
    if m:
        return f"E{m.group(1)}"
    return ""

def _extract_quality(text):
    m = re.search(r"(1080p|720p|480p|4K|2160p)", text, re.IGNORECASE)
    return m.group(1) if m else "HD"

def mlsbd(title, tmdb_id="", season=0, episode=0, year="", media_type=""):
    sources = []
    for domain in MLSBD_DOMAINS:
        html = _fetch(f"{domain}/?s={title}", headers={"Referer": domain})
        if not html:
            continue
        soup = BeautifulSoup(html, "lxml")

        post_url = None

        for a in soup.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if domain in href and title.split()[0].lower() in text.lower() and href != f"{domain}/" and href != domain:
                if title_matches_search(text, title, query_year=year):
                    post_url = href
                    break
        if not post_url:
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                text = a.get_text(strip=True).lower()
                if domain in href and title.split()[0].lower() in text and href != f"{domain}/" and href != domain:
                    post_url = href
                    break
        if not post_url:
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if domain in href and "/?s=" not in href and href != domain and href != f"{domain}/":
                    post_url = href
                    break
        if not post_url:
            continue

        post_html = _fetch(post_url, headers={"Referer": domain})
        if not post_html:
            continue

        meta = _extract_post_metadata(post_html)
        post_soup = BeautifulSoup(post_html, "lxml")
        lang = meta.get("language", "")

        all_elements = post_soup.select("h2, h3, h4, h5, strong, b, a[href]")
        current_ep = ""

        for el in all_elements:
            el_text = el.get_text(strip=True)
            ep = _parse_episode_from_text(el_text)
            if ep:
                current_ep = ep
                continue

            if el.name != 'a':
                continue
            href = el.get("href", "")
            if not href or not any(x in href for x in ["savelinks", "filepress", "gdflix", "pixeldrain", "mega", "drive", "bonghd"]):
                continue

            quality = _extract_quality(el_text)
            file_size = _match_size_to_quality(quality, meta)

            ep_label = current_ep

            if "savelinks" in href:
                resolved = _resolve_savelinks(href)
                for link in resolved:
                    if "gdflix" in link:
                        gdflix_resolved = resolve_gdflix(link, quality=quality, referer=href)
                        if gdflix_resolved:
                            for g in gdflix_resolved:
                                if lang and not g.get("language"):
                                    g["language"] = lang
                                if file_size and not g.get("fileSize"):
                                    g["fileSize"] = file_size
                                if ep_label:
                                    g["episode_label"] = ep_label
                                sources.append(g)
                    elif "hubcloud" in link or "hubdrive" in link:
                        res = resolve_any(link, quality=quality, referer=href)
                        if res:
                            for r in res:
                                if lang and not r.get("language"): r["language"] = lang
                                if file_size and not r.get("fileSize"): r["fileSize"] = file_size
                                if ep_label: r["episode_label"] = ep_label
                                sources.append(r)
                    elif "filepress" in link or _is_streamable(link):
                        base = {"url": link, "quality": quality, "provider": "MLSBD", "format": "mp4"}
                        if lang: base["language"] = lang
                        if file_size: base["fileSize"] = file_size
                        if ep_label: base["episode_label"] = ep_label
                        sources.append(base)
                if not resolved:
                    base = {"url": href, "quality": quality, "provider": "MLSBD", "format": "mp4"}
                    if lang: base["language"] = lang
                    if ep_label: base["episode_label"] = ep_label
                    sources.append(base)
            else:
                fmt = "mkv" if ".mkv" in href or "mkv" in el_text.lower() else "mp4"
                if "gdflix" in href:
                    gdflix_resolved = resolve_gdflix(href, quality=quality, referer=post_url)
                    if gdflix_resolved:
                        for g in gdflix_resolved:
                            if lang and not g.get("language"):
                                g["language"] = lang
                            if file_size and not g.get("fileSize"):
                                g["fileSize"] = file_size
                            if ep_label:
                                g["episode_label"] = ep_label
                            sources.append(g)
                    else:
                        base = {"url": href, "quality": quality, "provider": "MLSBD", "format": fmt}
                        if lang: base["language"] = lang
                        if file_size: base["fileSize"] = file_size
                        if ep_label: base["episode_label"] = ep_label
                        sources.append(base)
                elif _is_streamable(href):
                    base = {"url": href, "quality": quality, "provider": "MLSBD", "format": fmt}
                    if lang: base["language"] = lang
                    if file_size: base["fileSize"] = file_size
                    if ep_label: base["episode_label"] = ep_label
                    sources.append(base)

        if sources:
            break

    scored = []
    for s in sources:
        sc = score_content(s.get("url", ""), title, year, media_type)
        if sc >= 15 or year:
            s["relevance_score"] = max(sc, 15)
            scored.append(s)
        elif not year and sources:
            s["relevance_score"] = 15
            scored.append(s)
    scored.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return scored[:10]
