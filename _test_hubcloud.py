import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session
from bs4 import BeautifulSoup
import re

# Fetch hubcloud page
url = "https://hubcloud.foo/drive/r1vo29ystqohoqh"
r = cf_get(url, timeout=15)
print("hubcloud: {} bytes".format(len(r) if r else 0))

if r:
    soup = BeautifulSoup(r, "lxml")
    
    # Find card-header (file info)
    for el in soup.select("[class*=card-header]"):
        print("  card-header: {}".format(el.get_text(strip=True)[:80]))
    
    # Find download button (#download href or var url)
    btn = soup.select_one("#download")
    if btn:
        print("  #download href: {}".format(btn.get("href","")[:80]))
    
    # Find var url pattern
    for m in re.finditer(r"var url = '([^']+)'", r):
        print("  var url: {}".format(m.group(1)[:100]))
    
    # Find ALL btn links (like the plugin does: a.btn, a.btn-lg, etc.)
    for cls in ["btn", "btn-lg", "btn-primary", "btn-success", "btn-danger"]:
        for a in soup.select("a.{}".format(cls)):
            h = a.get("href","")
            t = a.get_text(strip=True)
            if h and not h.startswith("#"):
                print("  [{}] {} | {}".format(cls, h[:80], t[:40]))
    
    # Also check for FSL-related text
    if "fsl" in r.lower() or "FSL" in r:
        for m in re.finditer(r'(?:fsl|FSL|Fsl)[^<"]*', r):
            print("  FSL: {}".format(m.group().strip()[:80]))
