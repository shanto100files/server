import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

r = cf_get("https://vcloud.zip/vyjyrddiwcsyuy1", timeout=15)
soup = BeautifulSoup(r, "lxml")

# Print ALL links
for a in soup.find_all("a", href=True):
    h = a["href"]
    t = a.get_text(strip=True)[:40]
    if h != "#" and not h.startswith("javascript") and not h.startswith("http"):
        continue
    if any(x in h.lower() for x in ["css", "js?", "fonts", "favicon", "bootstrap", "jquery"]):
        continue
    print("  {} | {}".format(h[:100], t))

# Print all h1-h6 content
for tag in ["h1","h2","h3","h4","h5","h6"]:
    for el in soup.find_all(tag):
        print("  {}: {}".format(tag, el.get_text(strip=True)[:80]))
        
# Check for links with download/file patterns
for a in soup.find_all("a", href=True):
    h = a["href"]
    t = a.get_text(strip=True).lower()
    if any(x in h.lower() for x in ["download", "file", "dl/", "get"]):
        print("  DL-LINK: {} | {}".format(h[:100], a.get_text(strip=True)[:50]))
