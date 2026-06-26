import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from client import cf_get
from providers.hubcloud import extract_hubcloud
from providers.gdflix import resolve_gdflix

BASE = "https://www.animedubhindi.cc"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def _soup(url):
    html = cf_get(url, headers={"Referer": BASE, "User-Agent": UA}, timeout=20)
    if not html:
        raise Exception(f"Failed to fetch {url}")
    return BeautifulSoup(html, "html.parser")

def search(query):
    try:
        soup = _soup(f"{BASE}/?s={query}")
        results = []
        for article in soup.select("article"):
            a = article.select_one("h2 a")
            img = article.select_one("img")
            if not a:
                continue
            title = a.text.strip()
            href = a["href"] if a.get("href") else ""
            poster = img.get("src") or img.get("data-src") or "" if img else ""
            results.append({
                "id": href,
                "title": re.sub(r'\s*\(\d{4}\)$', '', title).strip(),
                "poster": poster,
                "url": href,
            })
        return results
    except Exception as e:
        return []

def home():
    try:
        soup = _soup(BASE)
        sections = []
        for section in soup.select("div.carousel, section"):
            heading = section.select_one("h2, h3")
            if not heading:
                continue
            title = heading.text.strip()
            items = []
            for article in section.select("article"):
                a = article.select_one("h2 a")
                img = article.select_one("img")
                if not a:
                    continue
                items.append({
                    "id": a["href"] if a.get("href") else "",
                    "title": a.text.strip(),
                    "poster": img.get("src") or img.get("data-src") or "" if img else "",
                    "url": a["href"] if a.get("href") else "",
                })
            if items:
                sections.append({"title": title, "items": items})
        return sections
    except Exception as e:
        return []

def info(url):
    try:
        soup = _soup(url)
        title = soup.select_one("meta[property=og:title]")
        title = title["content"].strip() if title else ""
        description = soup.select_one("div.entry-content p")
        description = description.text.strip() if description else ""
        poster = soup.select_one("div.entry-content img")
        poster = poster.get("src") or "" if poster else ""

        info_map = {}
        for li in soup.select("ul.wp-block-list li"):
            strong = li.select_one("strong")
            if strong:
                key = strong.text.strip().rstrip(":")
                value = li.own_text().strip()
                info_map[key] = value

        genres = [g.strip() for g in info_map.get("Genres", "").split("|") if g.strip()]
        rating = info_map.get("MAL Rating", "").split("/")[0] or info_map.get("IMDb Rating", "").split("/")[0]

        iframe_url = ""
        iframe_a = soup.select_one("div.wp-block-button a")
        if iframe_a and iframe_a.get("href"):
            iframe_url = iframe_a["href"]

        is_movie = "movie" in url.lower() or "Movie" in title

        episodes = []
        if iframe_url and not is_movie:
            ep_soup = _soup(iframe_url)
            for card in ep_soup.select("div.pro-ep-card"):
                ep_text = card.select_one(".pro-ep-title")
                ep_num = 0
                if ep_text:
                    m = re.search(r"Episode:\s*(\d+)", ep_text.text)
                    if m:
                        ep_num = int(m.group(1))
                links = []
                for a in card.select(".pro-btn-group a"):
                    href = a.get("href", "")
                    if "hubcloud" in href or "gdflix" in href:
                        links.append({"server": a.text.strip(), "url": href})
                if links:
                    episodes.append({"episode": ep_num, "links": links})

            for block in ep_soup.select("div.wp-block-group"):
                ep_text = block.select_one("h2")
                if not ep_text or "Episode" not in ep_text.text:
                    continue
                m = re.search(r"Episode:\s*(\d+)", ep_text.text)
                ep_num = int(m.group(1)) if m else 0
                links = []
                for a in block.select("a"):
                    href = a.get("href", "")
                    if "hubcloud" in href or "gdflix" in href:
                        links.append({"server": a.text.strip(), "url": href})
                if links:
                    episodes.append({"episode": ep_num, "links": links})

        sources = []
        if is_movie and iframe_url:
            mov_soup = _soup(iframe_url)
            for card in mov_soup.select("div.pro-ep-card .pro-quality-wrapper"):
                quality_el = card.select_one(".pro-ep-quality")
                quality = quality_el.text.strip("[]") if quality_el else ""
                for a in card.select(".pro-btn-group a"):
                    href = a.get("href", "")
                    if "hubcloud" in href or "gdflix" in href:
                        sources.append({"server": f"{a.text.strip()} {quality}".strip(), "url": href})
            for h4 in mov_soup.select("div.entry-content h4"):
                quality = h4.own_text().strip()
                for a in h4.select("a"):
                    href = a.get("href", "")
                    if "hubcloud" in href or "gdflix" in href:
                        sources.append({"server": f"{a.text.strip()} {quality}".strip(), "url": href})

        return {
            "title": title,
            "poster": poster,
            "description": description,
            "genres": genres,
            "rating": rating,
            "info": info_map,
            "is_movie": is_movie,
            "episodes": sorted(episodes, key=lambda x: x["episode"]),
            "sources": sources,
            "iframe_url": iframe_url,
        }
    except Exception as e:
        return {"error": str(e)}

def resolve_links(links):
    results = []
    for link in links:
        url = link.get("url", "")
        server = link.get("server", "Unknown")
        if "hubcloud" in url:
            resolved = extract_hubcloud(url)
            for r in resolved:
                r["server"] = f"HubCloud - {r.get('server', 'Direct')}"
                results.append(r)
        elif "gdflix" in url:
            resolved = resolve_gdflix(url)
            for r in resolved:
                r["server"] = f"GDFlix - {server}"
                results.append(r)
        else:
            results.append({"url": url, "server": server, "quality": "HD", "provider": "Direct", "format": "mp4"})
    return results
