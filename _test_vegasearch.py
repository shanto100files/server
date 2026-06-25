import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
import re

# Search vegamovies for The Batman
html = cf_get("https://vegamovies.mq/?s=The+Batman&page=1", timeout=15)
print("Search: {} bytes".format(len(html) if html else 0))
if html:
    # Find post links
    for m in re.finditer(r'<a\s+href="([^"]+)"[^>]*>\s*<div class="poster-card">', html):
        print("Post: {}".format(m.group(1)[:100]))
    # Also try finding download links
    for m in re.finditer(r'<a[^>]*href="([^"]*(?:vcloud|hubcloud|fast-dl|fastdl)[^"]*)"', html):
        print("DL: {}".format(m.group(1)[:100]))
