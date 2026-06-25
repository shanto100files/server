import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
import re

html = cf_get("https://vegamovies.mq/?s=The+Batman&page=1", timeout=15)

# Find script tags and API endpoints
for m in re.finditer(r'(fetch|axios|api|xhr|ajax)\([^)]*', html):
    print("API call: {}".format(m.group()[:150]))

# Find search.php or API endpoint
for m in re.finditer(r'(search\.php|api|ajax)[^"\']*', html):
    print("Endpoint: {}".format(m.group()[:100]))

# Check the search.php endpoint used by the plugin
r2 = cf_get("https://vegamovies.mq/search.php?q=The+Batman&page=1", timeout=15)
print("\nsearch.php: {} bytes".format(len(r2) if r2 else 0))
if r2:
    print(r2[:1000])
