import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import _cffi_session
import re

url = "https://savelinks.me/view/Ds6P8KHGMr"
r = _cffi_session.get(url, impersonate="chrome", timeout=15)
print("All hoster links found:")
seen = set()
for m in re.finditer(r'href="(https?://[^"]*)"', r.text):
    href = m.group(1)
    from urllib.parse import urlparse
    host = urlparse(href).hostname or ""
    if host and host != "savelinks.me" and host not in seen:
        seen.add(host)
        print("  {}".format(host))
