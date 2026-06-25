import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

# Step 2: Fetch post page
t0 = time.time()
r = cf_get("https://vegamovies.mq/download-the-batman-2022-dual-audio-hindi-480p-720p-1080p-2160p-4k/", timeout=15)
print("Step 2 Post: {} bytes in {:.1f}s".format(len(r) if r else 0, time.time()-t0))

if r:
    soup = BeautifulSoup(r, "lxml")
    # Find nexdrive links
    for a in soup.find_all("a", href=True):
        h = a["href"]
        t = a.get_text(strip=True)
        if "nexdrive" in h:
            print("  nexdrive: {} | text={}".format(h[:90], t[:40]))
            break
