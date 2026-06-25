import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from providers.fourkhd import fourkhd

t0 = time.time()
results = fourkhd("The Batman", year="2022")
elapsed = time.time() - t0
print("Duration: {:.1f}s".format(elapsed))
print("Sources found: {}".format(len(results)))
for r in results[:10]:
    out = "[{quality}] {provider} | {format} | {url}".format(**r)
    print("  " + out[:130])
