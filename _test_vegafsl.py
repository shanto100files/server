import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session
from bs4 import BeautifulSoup
import re, json, urllib.parse

# Step 1: Search for The Batman
t0 = time.time()
r = cf_get("https://vegamovies.mq/search.php?q=The+Batman+2022&page=1", timeout=15)
data = json.loads(r.decode())
elapsed = time.time() - t0
print("Search: {} hits in {:.1f}s".format(data.get("found", 0), elapsed))

# Find the 2022 Batman
for hit in data.get("hits", []):
    doc = hit.get("document", {})
    title = doc.get("post_title", "")
    permalink = doc.get("permalink", "")
    if "2022" in title and "The Batman" in title:
        print("Match: {}".format(title[:100]))
        print("Permalink: {}".format(permalink))
        post_url = "https://vegamovies.mq" + permalink
        break

# Step 2: Fetch post page
t0 = time.time()
post_html = cf_get(post_url, timeout=15)
print("\nPost: {} bytes in {:.1f}s".format(len(post_html) if post_html else 0, time.time()-t0))

if post_html:
    # Find download buttons
    soup = BeautifulSoup(post_html, "lxml")
    
    # Find buttons with download classes (like the plugin does)
    for cls in ["dwd-button", "dwd", "btn", "download", "dl", "maxbutton"]:
        for btn in soup.select("a[class*=" + cls + "], button[class*=" + cls + "]"):
            href = btn.get("href", "") or btn.get("data-url", "") or btn.get("data-src", "")
            text = btn.get_text(strip=True)
            print("  [{}] href={} | text={}".format(cls, href[:80], text[:40]))
    
    # Also find all links with vcloud/hubcloud/fastdl/fsl patterns
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if any(x in h for x in ["vcloud", "hubcloud", "fastdl", "fsl", "nexdrive"]):
            print("  DL: {} | text={}".format(h[:90], a.get_text(strip=True)[:40]))
