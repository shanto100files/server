import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from providers.mlsbd import mlsbd

t0 = time.time()
results = mlsbd("Raakh", year="2026")
elapsed = time.time() - t0
print("Duration: {:.1f}s".format(elapsed))
print("Sources found: {}".format(len(results)))
for r in results[:15]:
    out = "[{quality}] {provider} | {url}".format(**r)
    if r.get("language"): out += " | lang=" + r["language"]
    if r.get("fileSize"): out += " | size=" + r["fileSize"]
    if r.get("episode_label"): out += " | ep=" + r["episode_label"]
    print("  " + out[:140])
