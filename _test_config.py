import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from providers.auto_resolver import is_direct_streamable, resolve_any, CONFIG

url = "https://streamtape.com/v/b3vvpbKAA0HLW9/test.mkv"
print("is_direct_streamable: {}".format(is_direct_streamable(url)))

directs = CONFIG.get("file_hosts", {}).get("direct_streamable", [])
print("Direct streamable hosts count: {}".format(len(directs)))
for d in directs:
    if "streamtape" in d.lower():
        print("  Found: {}".format(d))

# Check if any match
from urllib.parse import urlparse
host = urlparse(url).hostname or ""
for d in directs:
    d_clean = d.lstrip("*.")
    if d.startswith("*."):
        if host == d_clean or host.endswith("." + d_clean):
            print("Match: host={}, pattern={}".format(host, d))
    elif d == host:
        print("Exact match: {}".format(d))
