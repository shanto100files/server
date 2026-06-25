import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

r = cf_get("https://4khdhub.one/the-batman-movie-690/", timeout=15)
soup = BeautifulSoup(r, "lxml")

# Find ALL links with href
for a in soup.find_all("a", href=True):
    h = a["href"]
    t = a.get_text(strip=True)
    if h.startswith("http") and not any(x in h for x in [".css", ".js", "fonts", "google", "cloudfront", "cdn"]):
        if len(t) > 2 or "server" in h.lower() or "download" in h.lower() or "hub" in h.lower():
            print("  {} | {}".format(h[:100], t[:50]))
