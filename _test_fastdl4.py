import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get

# Fetch the JS file that likely handles the download
js = cf_get("https://fast-dl.one/template/getlinkurl.js", timeout=10)
if js:
    print(js[:2000])
