import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
from providers.mlsbd import title_matches_search, _fetch, _extract_post_metadata, _resolve_savelinks, _extract_quality
from providers.auto_resolver import resolve_any, is_direct_streamable

# Step 1: Search
html = _fetch("https://mlsbd.co/?s=The+Batman", headers={"Referer": "https://mlsbd.co"})
soup = BeautifulSoup(html, "lxml")

# Step 2: Find post URL (like the code does)
post_url = None
domain = "https://mlsbd.co"
title = "The Batman"

for a in soup.select("a[href]"):
    href = a.get("href", "")
    text = a.get_text(strip=True)
    if domain in href and title.split()[0].lower() in text.lower() and href != domain + "/" and href != domain:
        if title_matches_search(text, title, query_year=""):
            post_url = href
            print("Found via title_matches: {}".format(post_url))
            break

if not post_url:
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True).lower()
        if domain in href and title.split()[0].lower() in text and href != domain + "/" and href != domain:
            post_url = href
            print("Found via fallback 1: {}".format(post_url))
            break

if not post_url:
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if domain in href and "/?s=" not in href and href != domain and href != domain + "/":
            post_url = href
            print("Found via fallback 2: {}".format(post_url))
            break

# Step 3: Fetch post page
print("\nPost URL: {}".format(post_url))
post_html = _fetch(post_url, headers={"Referer": domain})
print("Post HTML: {} bytes".format(len(post_html) if post_html else 0))

if post_html:
    # Step 4: Try to find links
    meta = _extract_post_metadata(post_html)
    print("Meta: {}".format(meta))
    post_soup = BeautifulSoup(post_html, "lxml")
    
    # Check what links exist
    found_links = []
    for a in post_soup.select("a[href]"):
        href = a.get("href", "")
        if not href: continue
        if any(x in href for x in ["savelinks", "filepress", "gdflix", "pixeldrain", "mega", "drive", "bonghd"]):
            found_links.append(href)
    print("Download links found: {}".format(len(found_links)))
    for l in found_links[:5]:
        print("  {}".format(l[:80]))
