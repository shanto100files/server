import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

url = "https://vcloud.zip/vyjyrddiwcsyuy1?token=SHRqbHRtejdUUGtDcWRNdHR3cDVHeGM0L2JLd2xjZXJuL1JkcHVoalVZWT0="
r = cf_get(url, timeout=15)
print("Token page: {} bytes".format(len(r) if r else 0))

if r:
    soup = BeautifulSoup(r, "lxml")
    
    # Find all h2 sections
    for h2 in soup.find_all("h2"):
        print("\nh2: {}".format(h2.get_text(strip=True)[:80]))
        # Find links in or after h2
        for a in h2.find_all_next("a", href=True):
            h = a["href"]
            t = a.get_text(strip=True)
            # Stop if we hit another h2
            if a.find_previous("h2") != h2:
                break
            if h.startswith("http"):
                print("  href={} | text={}".format(h[:80], t[:50]))
    
    # Find ALL links (excluding CSS/JS/etc)
    for a in soup.find_all("a", href=True):
        h = a["href"]
        t = a.get_text(strip=True)
        if h.startswith("http") and not any(x in h for x in [".css", ".js", "fonts", "favicon"]):
            if any(x in t.lower() for x in ["fsl", "mega", "buzz", "pixel", "server", "download", "direct", "cloud"]):
                print("\nServer link: {} | {}".format(h[:90], t[:50]))
    
    # Also check for obfuscated links
    for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', r):
        h = m.group(1)
        t = BeautifulSoup(m.group(2), "html.parser").get_text(strip=True)
        if h.startswith("http") and not any(x in h for x in [".css", ".js", "fonts", "favicon"]):
            if len(t) > 1 and t not in ["Copy Link", ""]:
                print("  link: {} | text={}".format(h[:80], t[:40]))
