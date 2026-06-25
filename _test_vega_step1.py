import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
import json

# Step 1: Search
t0 = time.time()
r = cf_get("https://vegamovies.mq/search.php?q=The+Batman+2022&page=1", timeout=10)
print("Step 1 Search: {} bytes in {:.1f}s".format(len(r) if r else 0, time.time()-t0))

if r:
    data = json.loads(r)
    print("Hits: {}".format(data.get("found", 0)))
    for hit in data.get("hits", []):
        doc = hit.get("document", {})
        t = doc.get("post_title", "")
        if "2022" in t and "The Batman" in t and "Doom" not in t:
            print("  Found: {}".format(t[:80]))
            print("  permalink: {}".format(doc.get("permalink","")))
