import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

# Try a different hubcloud drive (might have FSL)
hub_url = "https://hubcloud.foo/drive/y4kgtvnminjjy1e"
hub_html = cf_get(hub_url, timeout=15)
m = re.search(r"var url = '([^']+)'", hub_html)

if m:
    redirect_url = m.group(1)
    r = cf_get(redirect_url, headers={"Cookie": "xla=s4t", "Referer": hub_url}, timeout=15)
    soup = BeautifulSoup(r, "lxml")
    
    # Card header (file info)
    for el in soup.select("[class*=card-header]"):
        txt = el.get_text(strip=True).encode("ascii", "ignore").decode()
        print("card-header: {}".format(txt[:100]))
    
    # Find ALL server links
    results = []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        t = a.get_text(strip=True)
        if h.startswith("http") and not any(x in h for x in [".css", ".js", "cdn.", "fonts", "unpkg", "use.fontawesome", "favicon"]):
            clean_t = t.encode("ascii", "ignore").decode().strip()
            if any(x in (t + " " + h).lower() for x in ["fsl", "server", "download", "s3", "mega", "buzz", "pixel", "zip", "10gbps", "gpdl", "direct"]):
                results.append("{} | {}".format(h[:100], clean_t[:50]))
    
    print("Server links: {}".format(len(results)))
    for r_line in results:
        print("  " + r_line)
