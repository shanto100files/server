import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from providers.mlsbd import mlsbd

for title, year in [("The Batman", "2022"), ("Raakh", "2026")]:
    t0 = time.time()
    results = mlsbd(title, year=year)
    elapsed = time.time() - t0
    print("{}: Duration {:.1f}s, Sources: {}".format(title, elapsed, len(results)))
    for r in results[:5]:
        out = "[{quality}] {provider} | {url}".format(**r)
        if r.get("language"): out += " | lang=" + r["language"]
        print("  " + out[:120])
    print()
