import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import _cffi_session
import re

url = "https://fast-dl.one/dl/3f297d"
r = _cffi_session.get(url, impersonate="chrome", timeout=15, allow_redirects=True)
print("Status: {}".format(r.status_code))
print("Final URL: {}".format(r.url))
print("Headers: {}".format(dict(r.headers)))
print("Body: {} bytes".format(len(r.text)))
if r.text:
    for pat in [r'https?://[^""\s<>]*(?:\.mkv|\.mp4|\.avi|\.zip)[^""\s<>]*',
                r'href="(https?://[^"]*)"',
                r'src="(https?://[^"]*)"',
                r'url\s*[=:]\s*["\']([^"\']+)',
                r'downloadUrl[^=]*=[^"\']*["\']([^"\']+)']:
        found = re.findall(pat, r.text, re.IGNORECASE)
        if found:
            for f in found[:3]:
                print("  {}: {}".format(pat[:25], f[:100]))
