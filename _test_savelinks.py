import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session

url = "https://savelinks.me/view/Ds6P8KHGMr"

# Test cf_get
r1 = cf_get(url, headers={"Referer": "https://mlsbd.co"}, timeout=15)
print("cf_get: {} bytes".format(len(r1) if r1 else 0))
if r1:
    import re
    links = re.findall(r'href="(https?://[^"]*(?:filepress|gdflix|pixeldrain|mega|drive)[^"]*)"', r1)
    js_links = re.findall(r'"(https?://[^"]*(?:filepress|gdflix)[^"]*)"', r1)
    print("Links found via regex: {}".format(len(links + js_links)))
    for l in (links + js_links)[:5]:
        print("  {}".format(l[:80]))
else:
    # Test cffi
    r2 = _cffi_session.get(url, impersonate="chrome", timeout=10)
    print("cffi: Status={}, {} bytes".format(r2.status_code, len(r2.text)))
