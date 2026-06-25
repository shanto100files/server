import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session
import re

# Check vegamovies.phd
url = "https://vegamovies.phd/"
r = cf_get(url, timeout=10)
print("vegamovies.phd: {} bytes".format(len(r) if r else 0))
if r:
    # Check title
    m = re.search(r"<title>([^<]+)", r)
    if m: print("  Title: {}".format(m.group(1)))
    # Check for download links patterns
    links = re.findall(r'href="(https?://[^"]*(?:fast-dl|dl\.)[^"]*)"', r)
    print("  fast-dl links: {}".format(len(links)))
    for l in links[:5]:
        print("    {}".format(l[:100]))
        
    # Check for "id=" pattern
    ids = re.findall(r'id=([a-zA-Z0-9]+)', r)
    print("  IDs found: {}".format(len(ids)))
    for i in ids[:10]:
        print("    id={}".format(i))
