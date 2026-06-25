import sys, time, re
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get

# Step 3: Nexdrive page
nex_url = "https://nexdrive.pro/genxfm784776193762/"
t0 = time.time()
nex_html = cf_get(nex_url, timeout=15)
print("Step 3 Nexdrive: {} bytes in {:.1f}s".format(len(nex_html) if nex_html else 0, time.time()-t0))

if nex_html:
    # Find vcloud
    for m in re.finditer(r'href="(https?://vcloud\.zip/[^"]*)"', nex_html):
        print("  vcloud.zip: {}".format(m.group(1)[:90]))
    # Alternative: find any vcloud/hubcloud
    for m in re.finditer(r'href="(https?://[^"]*(?:hubcloud|vcloud)[^"]*)"', nex_html):
        h = m.group(1)
        if "signup" not in h and "tg/" not in h and "bit.ly" not in h:
            print("  alt: {}".format(h[:90]))
