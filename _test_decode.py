import sys, base64
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
import re

r = cf_get("https://vcloud.zip/vyjyrddiwcsyuy1", timeout=15)

# Find the double-base64 encoded URL
m = re.search(r"var\s+url\s*=\s*atob\(atob\(['\"]([^'\"]+)['\"]\)\)", r)
if m:
    b64_once = m.group(1)
    print("Double encoded: {}".format(b64_once[:60]))
    try:
        once = base64.b64decode(b64_once).decode()
        print("First decode: {}".format(once[:80]))
        # Sometimes base64 needs padding
        while len(once) % 4 != 0:
            once += "="
        final = base64.b64decode(once).decode()
        print("Final URL: {}".format(final))
    except Exception as e:
        print("Error: {}".format(e))
        # Try with padding
        try:
            b64_padded = b64_once
            while len(b64_padded) % 4 != 0:
                b64_padded += "="
            once = base64.b64decode(b64_padded).decode()
            print("With padding - first decode: {}".format(once[:80]))
            while len(once) % 4 != 0:
                once += "="
            final = base64.b64decode(once).decode()
            print("Final URL: {}".format(final))
        except Exception as e2:
            print("Error2: {}".format(e2))
else:
    print("Pattern not found, trying alternative...")
    # Try alternative base64 extraction
    for m2 in re.finditer(r'atob\(atob\(["\']([^"\']+)["\']\)\)', r):
        print("Found: {}".format(m2.group(1)[:60]))
