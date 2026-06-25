import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

url = "https://hubdrive.space/file/34407741688"
html = cf_get(url, timeout=15)
soup = BeautifulSoup(html, "lxml")

# Find all forms/buttons
for a in soup.find_all("a", href=True):
    h = a["href"]
    t = a.get_text(strip=True).encode("ascii", "ignore").decode().strip()
    if h.startswith("http") and "cdn." not in h and "fonts" not in h:
        print("{} | {}".format(h[:80], t[:40]))

# Find download button patterns from plugin
for el in soup.select("#download, [id*=download], .btn, a.btn, a[href*=hubcloud]"):
    print("el: {} | href={} | text={}".format(el.name, (el.get("href","") or "")[:80], el.get_text(strip=True)[:40]))
