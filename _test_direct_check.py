import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from providers.auto_resolver import is_direct_streamable, resolve_any
from urllib.parse import urlparse
from providers.domain_config import CONFIG

url = "https://streamtape.com/v/b3vvpbKAA0HLW9/test.mkv"
print("is_direct_streamable: {}".format(is_direct_streamable(url)))

host = urlparse(url).hostname
print("Host: {}".format(host))

directs = CONFIG.get("file_hosts", {}).get("direct_streamable", [])
print("Direct streamable hosts: {}".format(directs[:10]))

# Check if streamtape is in direct_streamable
for d in directs:
    if "streamtape" in d:
        print("Found streamtape in config: {}".format(d))
    if host.endswith(d.replace("*.", "")):
        print("Host {} matches {}".format(host, d))
