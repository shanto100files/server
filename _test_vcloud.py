import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session
from bs4 import BeautifulSoup
import re

url = "https://vcloud.zip/vyjyrddiwcsyuy1"

# Fetch the vcloud page
r = cf_get(url, timeout=15)
print("vcloud.zip: {} bytes".format(len(r) if r else 0))

if r:
    # Check for the card-header with file info (per plugin code)
    soup = BeautifulSoup(r, "lxml")
    
    # Find card-header elements (file name/size)
    for el in soup.select("[class*=card-header]"):
        print("  card-header: {}".format(el.get_text(strip=True)[:80]))
    
    # Find btn links (download buttons per plugin code)
    for el in soup.select("[class*=btn] a[href], a[class*=btn]"):
        href = el.get("href", "")
        text = el.get_text(strip=True)
        if href:
            print("  btn: {} | {}".format(href[:80], text[:50]))
    
    # Find all links with h2 context (plugin finds FSL, Mega, Buzz etc inside h2)
    # Plugin checks for: FSL Server, FSLv2, Mega, BuzzServer, Pixeldrain, 10Gbps, Download File
    for h2 in soup.find_all("h2"):
        h2_text = h2.get_text(strip=True)
        links_in_h2 = h2.find_all("a", href=True)
        for a in links_in_h2:
            print("  h2-link: {} | text={}".format(a["href"][:80], h2_text[:50]))
        if not links_in_h2:
            # Check next sibling for links
            nxt = h2.find_next_sibling()
            if nxt:
                for a in nxt.find_all("a", href=True):
                    print("  h2-sibling: {} | text={}".format(a["href"][:80], h2_text[:50]))
    
    # Direct link extraction
    for m in re.finditer(r'(https?://[^""\s<>]*(?:\.mp4|\.mkv|\.avi|download)[^""\s<>]*)', r):
        print("  direct: {}".format(m.group()[:100]))
        
    # Look for FSL references
    if "FSL" in r or "fsl" in r.lower():
        for m in re.finditer(r'(FSL[^<]*)', r):
            print("  FSL text: {}".format(m.group(1).strip()[:80]))
        for m in re.finditer(r'href="(https?://[^"]*)"[^>]*>([^<]*(?:FSL|fsl)[^<]*)<', r):
            print("  FSL link: {} | text={}".format(m.group(1)[:80], m.group(2).strip()[:50]))
