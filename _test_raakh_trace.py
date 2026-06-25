import sys, time, traceback
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re
from providers.mlsbd import _fetch, _extract_post_metadata, _resolve_savelinks, _extract_quality, _match_size_to_quality, _parse_episode_from_text
from providers.auto_resolver import title_matches_search
from providers.gdflix import resolve_gdflix, _is_streamable

title = "Raakh"
domain = "https://mlsbd.co"

# Step 1: Search
t0 = time.time()
html = _fetch(f"{domain}/?s={title}")
print("Search: {} bytes in {:.1f}s".format(len(html) if html else 0, time.time()-t0))

soup = BeautifulSoup(html, "lxml")
post_url = None
for a in soup.select("a[href]"):
    href = a.get("href", "")
    text = a.get_text(strip=True)
    if domain in href and title.split()[0].lower() in text.lower() and href != f"{domain}/" and href != domain:
        if title_matches_search(text, title, query_year=""):
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

print("Post URL: {}".format(post_url or "NOT FOUND"))

# Step 2: Fetch post
post_html = _fetch(post_url)
print("Post HTML: {} bytes".format(len(post_html) if post_html else 0))

# Step 3: Meta
meta = _extract_post_metadata(post_html)
print("Meta: {}".format(meta))

# Step 4: Find savelinks and process
post_soup = BeautifulSoup(post_html, "lxml")
all_elements = post_soup.select("h2, h3, h4, h5, strong, b, a[href]")
current_ep = ""

sources = []
seen_urls = set()

for el in all_elements:
    el_text = el.get_text(strip=True)
    ep = _parse_episode_from_text(el_text)
    if ep:
        current_ep = ep
        continue
    if el.name != "a":
        continue
    href = el.get("href", "")
    if not href or not any(x in href for x in ["savelinks", "filepress", "gdflix", "pixeldrain", "mega", "drive", "bonghd"]):
        continue
    if href in seen_urls:
        continue
    seen_urls.add(href)

    quality = _extract_quality(el_text)
    file_size = _match_size_to_quality(quality, meta)
    ep_label = current_ep

    print("\nProcessing: {} (quality={}, ep={})".format(href[:60], quality, ep_label))

    if "savelinks" in href:
        t1 = time.time()
        resolved = _resolve_savelinks(href)
        print("  _resolve_savelinks: {} links in {:.1f}s".format(len(resolved), time.time()-t1))
        for r in resolved:
            print("    resolved: {}".format(r[:80]))
            if "gdflix" in r:
                t2 = time.time()
                g_res = resolve_gdflix(r, quality=quality, referer=href)
                print("      resolve_gdflix: {} results in {:.1f}s".format(len(g_res), time.time()-t2))
                if g_res:
                    for g in g_res:
                        print("        -> {}".format(g.get("url","?")[:60]))

