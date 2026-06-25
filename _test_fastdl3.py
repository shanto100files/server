import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session
import re

url = "https://fast-dl.one/dl/3f297d"

# Try cf_get (cloudscraper)
r1 = cf_get(url, timeout=15)
print("cf_get: {} bytes".format(len(r1) if r1 else 0))
if r1:
    for m in re.finditer(r'(https?://[^""\s<>]+(?:\.mkv|\.mp4|\.zip|download|file|dl)[^""\s<>]*)', r1):
        print("  URL: {}".format(m.group()[:120]))

# Try POST (form submission)
r2 = _cffi_session.post(url, data={"submit": "1"}, impersonate="chrome", timeout=15, allow_redirects=True)
print("\nPOST /dl/3f297d: Status={}, URL={}".format(r2.status_code, r2.url))
if r2.status_code == 200 and r2.url != url:
    print("  Redirected to: {}".format(r2.url[:100]))

# Also try cf_get on the redirected URL
if "fast-dl.one" in str(r2.url):
    r3 = cf_get(r2.url, timeout=15)
    if r3:
        for m in re.finditer(r'(https?://[^""\s<>]+(?:\.mkv|\.mp4)[^""\s<>]*)', r3):
            print("  cf_get URL: {}".format(m.group()[:120]))
