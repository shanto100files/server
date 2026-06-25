import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

# Fetch The Batman post page
base = "https://4khdhub.one"
r = cf_get("{}/the-batman-movie-690/".format(base), timeout=15)
print("Post: {} bytes".format(len(r) if r else 0))

if r:
    # Find download links
    for m in re.finditer(r'href="(https?://[^"]*)"[^>]*>([^<]*)</a>', r):
        h = m.group(1)
        t = m.group(2).strip()
        if any(x in h for x in ["hubcloud", "gadgetsweb", "pixeldrain", "mega", "gpdl"]):
            print("  DL: {} | text={}".format(h[:90], t[:40]))
        elif any(x in t.lower() for x in ["download", "1080p", "4k", "2160p", "720p", "480p", "fsl", "server"]):
            if h.startswith("http"):
                print("  TXT: {} | text={}".format(h[:90], t[:40]))
