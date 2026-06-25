import sys, time
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session
import re

# Use the correct post URL
post_url = "https://mlsbd.co/raakh-2026-s01-hindi-amazon-web-dl-480p-720p-1080p-x264-850mb-2-3gb-6gb-download-watch-online/"
post_html = cf_get(post_url, headers={"Referer": "https://mlsbd.co"}, timeout=15)
print("Post HTML: {} bytes".format(len(post_html) if post_html else 0))

if post_html:
    savelinks = re.findall(r'href="(https?://savelinks\.me/[^"]*)"', post_html)
    print("savelinks URLs found: {}".format(len(savelinks)))
    for sl in savelinks[:3]:
        print("  {}".format(sl))
        sl_html = cf_get(sl, headers={"Referer": "https://mlsbd.co"}, timeout=15)
        if sl_html:
            # Check for gdflix
            if "gdflix" in sl_html:
                gd = re.findall(r'href="(https?://[^"]*gdflix[^"]*)"', sl_html)
                print("    gdflix links: {}".format(len(gd)))
                for g in gd:
                    print("      {}".format(g[:90]))
            # Check streamable links
            for m in re.finditer(r'href="(https?://[^"]*)"', sl_html):
                href = m.group(1)
                if "savelinks" not in href and "mlsbd" not in href and "/build/" not in href:
                    print("    -> {}".format(href[:90]))
