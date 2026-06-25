import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

hub_url = "https://hubcloud.foo/drive/r1vo29ystqohoqh"
hub_html = cf_get(hub_url, timeout=15)
m = re.search(r"var url = '([^']+)'", hub_html)
redirect_url = m.group(1)

r = cf_get(redirect_url, headers={"Cookie": "xla=s4t", "Referer": hub_url}, timeout=15)
soup = BeautifulSoup(r, "lxml")

# card-header
for el in soup.select("[class*=card-header]"):
    print("card-header: {}".format(el.get_text(strip=True)[:100]))

# size
for el in soup.select("#size, [id*=size]"):
    print("size: {}".format(el.get_text(strip=True)[:50]))

# Find ALL btn links
for a in soup.find_all("a", href=True):
    h = a["href"]
    t = a.get_text(strip=True)
    if h.startswith("http") and not any(x in h for x in [".css", ".js", "cdn.", "fonts", "unpkg", "use.fontawesome"]):
        if any(x in (t + " " + h).lower() for x in ["fsl", "server", "download", "direct", "cloud", "mega", "buzz", "pixel", "s3", "zipdisk", "10gbps", "gpdl"]):
            print("  {} | {}".format(h[:100], t[:50]))
