import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get

html = cf_get("https://vegamovies.mq/?s=The+Batman&page=1", timeout=15)
# Look for the search API
print(html[:3000])
