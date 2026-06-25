import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session
import re

url = "https://nexdrive.pro/genxfm784776193762/"

# Try cf_get
r1 = cf_get(url, timeout=15)
print("cf_get: {} bytes".format(len(r1) if r1 else 0))
if r1:
    # Find vcloud/hubcloud links
    for m in re.finditer(r'href="(https?://[^"]*(?:vcloud|hubcloud)[^"]*)"', r1):
        print("vcloud: {}".format(m.group(1)[:100]))
    # Find nexdrive links
    for m in re.finditer(r'href="(https?://[^"]*(?:nexdrive|fastdl)[^"]*)"', r1):
        print("nexdrive/fastdl: {}".format(m.group(1)[:100]))

# Try cffi
r2 = _cffi_session.get(url, impersonate="chrome", timeout=15, allow_redirects=True)
print("\ncffi: Status={}, len={}".format(r2.status_code, len(r2.text)))
if r2.text:
    for m in re.finditer(r'href="(https?://[^"]*(?:vcloud|hubcloud)[^"]*)"', r2.text):
        print("vcloud/hubcloud: {}".format(m.group(1)[:100]))
    for m in re.finditer(r'href="(https?://[^"]*(?:nexdrive|fastdl)[^"]*)"', r2.text):
        print("nexdrive/fastdl: {}".format(m.group(1)[:100]))
