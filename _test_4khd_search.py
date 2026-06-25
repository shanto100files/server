import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

# Search for The Batman on 4khdhub.one
base = "https://4khdhub.one"
r = cf_get("{}/?s=The+Batman".format(base), timeout=15)
soup = BeautifulSoup(r, "lxml")

# Find post links - check the structure
print("=== Search results ===")
# Look for the plugin's pattern: items with poster cards or links
for a in soup.find_all("a", href=True):
    h = a["href"]
    t = a.get_text(strip=True)
    if "/the-batman" in h.lower() or "/batman-" in h.lower():
        if len(t) > 5:
            print("  {} | {}".format(h[:80], t[:60]))

# Also find download buttons/links structure on post page
print("\n=== Post page ===")
r2 = cf_get("{}/the-batman-movie-690/".format(base), timeout=15)
soup2 = BeautifulSoup(r2, "lxml")

# Find hubcloud and hubdrive links
for a in soup2.find_all("a", href=True):
    h = a["href"]
    t = a.get_text(strip=True)
    if "hubcloud" in h or "hubdrive" in h:
        print("  DL: {}".format(h[:90]))
