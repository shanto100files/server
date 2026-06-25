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

# Save full HTML for analysis
with open(r"E:\cinepix\termux-server\_hubcloud_analysis.html", "w", encoding="utf-8") as f:
    f.write(r)

# Find all quality sections
soup = BeautifulSoup(r, "lxml")
body = soup.find("body")

# Find all h2 elements and their links
for i, h2 in enumerate(body.find_all("h2")):
    txt = h2.get_text(strip=True).encode("ascii", "ignore").decode()
    print("\n--- H2 #{}: {} ---".format(i, txt[:100]))
    nxt = h2.find_next_sibling()
    if nxt:
        for a in nxt.find_all("a", href=True):
            h = a["href"]
            t = a.get_text(strip=True).encode("ascii", "ignore").decode()
            if h.startswith("http") and "cdn." not in h and "fonts" not in h and "unpkg" not in h and "use.fontawesome" not in h:
                print("  {} | {}".format(h[:100], t[:40]))
