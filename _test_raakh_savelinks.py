import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session
from bs4 import BeautifulSoup
import re, time

# Check Raakh search
html = cf_get("https://mlsbd.co/?s=Raakh", headers={"Referer": "https://mlsbd.co"}, timeout=10)
soup = BeautifulSoup(html, "lxml")

# Find post URL
for a in soup.select("a[href]"):
    href = a.get("href", "")
    text = a.get_text(strip=True).lower()
    if "mlsbd.co" in href and "raakh" in href.lower():
        print("Found: {} | text: {}".format(href, a.get_text(strip=True)[:60]))
        break

# Now fetch savelinks from that post
post_url = "https://mlsbd.co/raakh-2025-dual-audio-hindi-english-web-dl-480p-720p-1080p-x264-450mb-1-4gb-3-2gb-esub-download-watch-online/"
post_html = cf_get(post_url, headers={"Referer": "https://mlsbd.co"}, timeout=15)
print("\nPost HTML: {} bytes".format(len(post_html) if post_html else 0))

if post_html:
    savelinks = re.findall(r'href="(https?://savelinks\.me/[^"]*)"', post_html)
    print("savelinks URLs found: {}".format(len(savelinks)))
    for sl in savelinks:
        print("  {}".format(sl))
        
        # Fetch savelinks page
        sl_html = cf_get(sl, headers={"Referer": "https://mlsbd.co"}, timeout=15)
        if sl_html:
            # Find all hoster links
            for m in re.finditer(r'href="(https?://[^"]*)"', sl_html):
                href = m.group(1)
                if "savelinks" not in href and "mlsbd" not in href and "/build/" not in href:
                    print("    -> {}".format(href[:100]))
