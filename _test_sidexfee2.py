import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session
import re, base64

url = "https://web.sidexfee.com/?id=3f297d"

# Try cffi first
t0 = time.time()
try:
    r = _cffi_session.get(url, impersonate="chrome", timeout=20, allow_redirects=True)
    body = r.text
    print("cffi: Status={}, {} bytes, {:.1f}s".format(r.status_code, len(body), time.time()-t0))
    
    m = re.search(r'link":"([^"]+)"', body)
    if m:
        b64 = m.group(1).replace("\\/", "/")
        while len(b64) % 4 != 0: b64 += "="
        try:
            decoded = base64.b64decode(b64).decode()
            print("Decoded link: {}".format(decoded))
        except Exception as e:
            print("Decode error: {} | raw: {}".format(e, b64[:80]))
    else:
        print("No link. Body: {}".format(body[:500]))
except Exception as e:
    print("cffi error: {} - {:.1f}s".format(e, time.time()-t0))
