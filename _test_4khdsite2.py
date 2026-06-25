import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

base = "https://4khdhub.one"
r = cf_get("{}/?s=The+Batman".format(base), timeout=15)
print("Search: {} bytes".format(len(r) if r else 0))

if r:
    soup = BeautifulSoup(r, "lxml")
    # Find post cards
    for article in soup.select("article, .post-card, .poster-card, [class*=post]"):
        a = article.find("a", href=True)
        if a:
            h = a["href"]
            t = a.get_text(strip=True)
            if "batman" in h.lower() or "batman" in t.lower():
                print("  post: {} | {}".format(h[:100], t[:60]))
    
    # Also check for the plugin's post card pattern
    for m in re.finditer(r'<a\s+href="([^"]+)"[^>]*>([\s\S]*?)</a>', r):
        h = m.group(1)
        t = BeautifulSoup(m.group(2), "html.parser").get_text(strip=True)
        if "batman" in h.lower() or "batman" in t.lower():
            if "/?s=" not in h and h != "#":
                print("  link: {} | text={}".format(h[:90], t[:50]))

    # Print first 3000 chars to understand structure
    print("\n--- First 3000 chars ---")
    print(r[:3000])
