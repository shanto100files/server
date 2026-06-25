import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from providers.fourkhd import fourkhd

for title, year in [("Deadpool", "2024"), ("Mufasa", "2024"), ("Interstellar", "2014")]:
    t0 = time.time()
    results = fourkhd(title, year=year)
    elapsed = time.time() - t0
    print("{}: {:.1f}s, {} sources".format(title, elapsed, len(results)))
    for r in results[:3]:
        print("  [{}] {} | {}".format(r["quality"], r["url"][:90], r["format"]))
    print()
