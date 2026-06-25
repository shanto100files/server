import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

# First fetch the hubcloud page to get the valid token
hub_url = "https://hubcloud.foo/drive/r1vo29ystqohoqh"
hub_html = cf_get(hub_url, timeout=15)

# Extract the download URL from hubcloud page
redirect_url = None
if hub_html:
    m = re.search(r"var url = '([^']+)'", hub_html)
    if m:
        redirect_url = m.group(1)
        print("Extracted URL: {}".format(redirect_url[:100]))

if redirect_url:
    # Fetch with proper cookie and referer
    r = cf_get(redirect_url, headers={
        "Cookie": "xla=s4t",
        "Referer": hub_url
    }, timeout=15)
    print("\nResponse: {} bytes".format(len(r) if r else 0))
    if r:
        print(r[:2000])
