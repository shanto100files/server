import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
import re, json

# Check 4khdhub.link and dynamic domain
dy = cf_get("https://raw.githubusercontent.com/SaurabhKaperwan/Utils/refs/heads/main/urls.json", timeout=8)
if dy:
    domains = json.loads(dy)
    print("4khdhub from urls.json:", domains.get("4khdhub", "not found"))
    print("hubcloud:", domains.get("hubcloud", "not found"))

# Test search
base = domains.get("4khdhub", "https://4khdhub.link")
r = cf_get("{}/?s=The+Batman".format(base), timeout=15)
print("\nSearch: {} bytes".format(len(r) if r else 0))
if r:
    # Find post links and download links
    for m in re.finditer(r'<a\s+href="([^"]+)"[^>]*>([^<]*)</a>', r):
        h = m.group(1)
        t = m.group(2).strip()
        if any(x in h for x in ["the-batman", "batman"]) and len(t) > 5:
            print("  post: {} | {}".format(h[:80], t[:40]))
