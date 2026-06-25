import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session

url = "https://gamerxyt.com/hubcloud.php?host=hubcloud&id=r1vo29ystqohoqh&token=TS85MW54NzExeFZ2NEVVUkt2TE9iTFJERkdRc0U0amhOdzNmVzRJOEo5OD0="

# Try cf_get
r1 = cf_get(url, timeout=15)
print("cf_get: {} bytes".format(len(r1) if r1 else 0))
if r1:
    print(r1[:500])

# Try cffi (might follow redirects better)
r2 = _cffi_session.get(url, impersonate="chrome", timeout=15, allow_redirects=True)
print("\ncffi: Status={}, URL={}, {} bytes".format(r2.status_code, r2.url, len(r2.text)))
if r2.text:
    print(r2.text[:500])
