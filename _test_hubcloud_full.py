import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

# First get hubcloud page and extract redirect URL
hub_url = "https://hubcloud.foo/drive/r1vo29ystqohoqh"
hub_html = cf_get(hub_url, timeout=15)
m = re.search(r"var url = '([^']+)'", hub_html)
redirect_url = m.group(1)

r = cf_get(redirect_url, headers={"Cookie": "xla=s4t", "Referer": hub_url}, timeout=15)
soup = BeautifulSoup(r, "lxml")

# Print the full body HTML structure to see ALL sections
body = soup.find("body")
if body:
    # Print all h2 tags and their following content
    for h2 in body.find_all("h2"):
        print("\n=== H2: {} ===".format(h2.get_text(strip=True)[:80]))
        # Get parent and find all links within the same parent div
        parent = h2.find_parent()
        if parent:
            for a in parent.find_all("a", href=True):
                h = a["href"]
                t = a.get_text(strip=True)
                if h.startswith("http") and not any(x in h for x in [".css", ".js", "cdn.", "fonts", "unpkg", "use.fontawesome", "favicon"]):
                    print("  {} | {}".format(h[:90], t[:40]))
    
    # Print all card-body / card sections
    for card in body.select("[class*=card], [class*=panel]"):
        header = card.select_one("[class*=card-header], [class*=panel-heading]")
        if header:
            print("\n=== Card: {} ===".format(header.get_text(strip=True)[:80]))
        for a in card.find_all("a", href=True):
            h = a["href"]
            t = a.get_text(strip=True)
            if h.startswith("http") and not any(x in h for x in [".css", ".js", "cdn.", "fonts", "unpkg", "use.fontawesome"]):
                print("  {} | {}".format(h[:90], t[:40]))
    
    # Also find links with text containing server names
    for a in body.find_all("a", href=True):
        h = a["href"]
        t = a.get_text(strip=True).lower()
        if h.startswith("http") and not any(x in h for x in [".css", ".js", "cdn.", "fonts", "unpkg", "use.fontawesome"]):
            if any(x in t for x in ["fsl", "server", "download", "direct", "s3", "mega", "buzz", "pixel", "zip", "10gbps", "gpdl"]):
                print("  ALL: {} | {}".format(h[:90], a.get_text(strip=True)[:40]))
