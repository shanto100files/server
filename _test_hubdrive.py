import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

# Check hubdrive.space instead
url = "https://hubdrive.space/file/34407741688"
drv_html = cf_get(url, timeout=15)
print("hubdrive: {} bytes".format(len(drv_html) if drv_html else 0))

if drv_html:
    soup = BeautifulSoup(drv_html, "lxml")
    for el in soup.select("[class*=card-header]"):
        txt = el.get_text(strip=True).encode("ascii", "ignore").decode()
        print("card-header: {}".format(txt[:100]))
    
    # Find download button / var url
    btn = soup.select_one("#download")
    if btn:
        print("#download href: {}".format(btn.get("href","")[:80]))
    m = re.search(r"var url = '([^']+)'", drv_html)
    if m:
        redirect = m.group(1)
        print("var url: {}".format(redirect[:100]))
        
        r2 = cf_get(redirect, headers={"Cookie": "xla=s4t", "Referer": url}, timeout=15)
        if r2:
            soup2 = BeautifulSoup(r2, "lxml")
            for el in soup2.select("[class*=card-header]"):
                txt = el.get_text(strip=True).encode("ascii", "ignore").decode()
                print("  card-header: {}".format(txt[:80]))
            
            # Server links
            for a in soup2.find_all("a", href=True):
                h = a["href"]
                t = a.get_text(strip=True)
                if h.startswith("http") and not any(x in h for x in [".css", ".js", "cdn.", "fonts", "unpkg", "use.fontawesome", "favicon"]):
                    clean_t = t.encode("ascii", "ignore").decode().strip()
                    if any(x in (t + " " + h).lower() for x in ["fsl", "server", "download", "s3", "mega", "buzz", "pixel", "zip", "10gbps", "gpdl", "direct"]):
                        print("  {} | {}".format(h[:100], clean_t[:50]))
