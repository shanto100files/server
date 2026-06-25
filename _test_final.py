import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from providers.mlsbd import mlsbd

t0 = time.time()
results = mlsbd("The Batman")
elapsed = time.time() - t0
print("Duration: {:.1f}s".format(elapsed))
print("Sources found: {}".format(len(results)))
for r in results[:10]:
    out = "{quality} | {url}".format(**r)
    if r.get("language"): out += " | lang=" + r["language"]
    if r.get("fileSize"): out += " | size=" + r["fileSize"]
    if r.get("episode_label"): out += " | ep=" + r["episode_label"]
    print("  " + out)
