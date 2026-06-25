import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")

# Simulate server search call
from server import search_all

t0 = time.time()
results = search_all("The Batman", year="2022", season=0, episode=0, media_type="movie", page=1)
elapsed = time.time() - t0
print("Duration: {:.1f}s".format(elapsed))
print("Total sources found: {}".format(len(results)))
for r in results[:15]:
    out = "[{quality}] {provider} | {url}".format(**r)
    if r.get("language"): out += " | lang=" + r["language"]
    if r.get("fileSize"): out += " | size=" + r["fileSize"]
    print("  " + out[:130])
