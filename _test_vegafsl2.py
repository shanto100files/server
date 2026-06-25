import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re, json

# Step 1: Search
r = cf_get("https://vegamovies.mq/search.php?q=The+Batman+2022&page=1", timeout=15)
data = json.loads(r)
print("Search: {} hits".format(data.get("found", 0)))

post_url = ""
for hit in data.get("hits", []):
    doc = hit.get("document", {})
    title = doc.get("post_title", "")
    if "2022" in title and "The Batman" in title and "Doom" not in title:
        permalink = doc.get("permalink", "")
        post_url = "https://vegamovies.mq" + permalink
        print("Match: {} | {}".format(title[:80], post_url))
        break

if not post_url:
    # Try first non-doom result
    for hit in data.get("hits", []):
        doc = hit.get("document", {})
        permalink = doc.get("permalink", "")
        title = doc.get("post_title", "")
        if "doom" not in permalink.lower():
            post_url = "https://vegamovies.mq" + permalink
            print("Fallback: {} | {}".format(title[:80], post_url))
            break

# Step 2: Fetch post
t0 = time.time()
post_html = cf_get(post_url, timeout=15)
print("\nPost: {} bytes in {:.1f}s".format(len(post_html) if post_html else 0, time.time()-t0))

if post_html:
    soup = BeautifulSoup(post_html, "lxml")
    
    # Find all download-type links per VegaMovies plugin pattern
    for cls in ["dwd-button", "dwd", "btn", "download", "dl", "maxbutton"]:
        for btn in soup.select("[class*=" + cls + "] a[href], a[class*=" + cls + "]"):
            href = btn.get("href", "")
            text = btn.get_text(strip=True)
            if href:
                print("  [{}] {} | {}".format(cls, href[:90], text[:50]))
    
    # Find ALL links with known patterns
    for a in soup.find_all("a", href=True):
        h = a["href"]
        t = a.get_text(strip=True)
        if any(x in h for x in ["vcloud", "hubcloud", "fastdl", "fsl", "nexdrive", "10gbps", "buzz"]):
            print("  DL: {} | {}".format(h[:100], t[:50]))
        elif any(x in t.lower() for x in ["fsl", "mega", "buzz", "pixel", "10gbps", "fast"]):
            print("  TXT: {} | {}".format(h[:100], t[:50]))
