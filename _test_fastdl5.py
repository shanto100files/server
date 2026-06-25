import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

html = cf_get("https://fast-dl.one/dl/3f297d", timeout=10)
soup = BeautifulSoup(html, "lxml")

# Print all links
for a in soup.find_all("a", href=True):
    h = a["href"]
    if h != "#" and not h.startswith("javascript"):
        print("  href: {} | text: {}".format(h[:100], a.get_text(strip=True)[:50]))

# Check for links containing specific patterns
for a in soup.find_all("a", href=True):
    h = a["href"]
    if any(x in h for x in [".mkv", ".mp4", "download", "dl/", "file", "get"]):
        print("\nDownload link: {} | text: {}".format(h[:120], a.get_text(strip=True)[:50]))

# Print the entire HTML structure (simplified)
print("\n--- Body content ---")
body = soup.find("body")
if body:
    print(body.get_text()[:2000])
