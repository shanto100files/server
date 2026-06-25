import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
import urllib.request
import base64
import json
import re

# Try the bypass API
url = "https://web.sidexfee.com/?id=3f297d"
r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15)
body = r.read().decode()
print("Response: {}".format(body[:300]))

# Extract the base64 link
m = re.search(r'link":"([^"]+)"', body)
if m:
    b64 = m.group(1).replace("\\/", "/")
    # Pad base64
    while len(b64) % 4 != 0:
        b64 += "="
    try:
        decoded = base64.b64decode(b64).decode()
        print("Decoded link: {}".format(decoded))
    except Exception as e:
        print("Base64 decode error: {}".format(e))
        print("Raw b64: {}".format(b64[:100]))
else:
    print("No link found in response")
