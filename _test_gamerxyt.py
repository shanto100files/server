import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session
from bs4 import BeautifulSoup
import re

# Fetch the hubcloud.php redirect URL
url = "https://gamerxyt.com/hubcloud.php?host=hubcloud&id=r1vo29ystqohoqh&token=TS85MW54NzExeFZ2NEVVUkt2TE9iTFJERkdRc0U0amhOdzNmVzRJOEo5OD0="
r = cf_get(url, timeout=15)
print("gamerxyt: {} bytes".format(len(r) if r else 0))

if r:
    soup = BeautifulSoup(r, "lxml")
    
    # card-header for file info
    for el in soup.select("[class*=card-header]"):
        print("  card-header: {}".format(el.get_text(strip=True)[:80]))
    for el in soup.select("h1, h2"):
        print("  {}: {}".format(el.name, el.get_text(strip=True)[:80]))
    
    # size
    for el in soup.select("#size, [id*=size]"):
        print("  size: {}".format(el.get_text(strip=True)[:50]))
    
    # Find ALL btn links (like Ot() function does)
    for cls in ["btn", "btn-lg", "btn-primary", "btn-success", "btn-danger"]:
        for a in soup.select("a.{}".format(cls)):
            h = a.get("href","")
            t = a.get_text(strip=True)
            if h and h.startswith("http"):
                print("  [{}] {} | text={}".format(cls, h[:100], t[:50]))
    
    # Check for FSL / server patterns
    for m in re.finditer(r'(?:fsl|FSL|Fsl|server|Server)[^<"\']*', r):
        print("  found: {}".format(m.group().strip()[:80]))
