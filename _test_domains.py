import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get

# Check which domains work
for d in ["https://vegamovies.mq", "https://vegamovie.sl", "https://vegamovies.tel", "https://vegamovies.market"]:
    r = cf_get(d + "/", timeout=10)
    print("{}: {} bytes".format(d, len(r) if r else 0))
