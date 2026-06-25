import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import _cffi_session
import re

# Fetch savelinks page
url = "https://savelinks.me/view/Ds6P8KHGMr"
r = _cffi_session.get(url, impersonate="chrome", timeout=15, allow_redirects=True)
print("Status: {}, URL: {}".format(r.status_code, r.url))
print("Body length: {}".format(len(r.text)))
print()

# Print all links
for m in re.finditer(r'href="(https?://[^"]*)"', r.text):
    href = m.group(1)
    txt_before = r.text[max(0, m.start()-40):m.start()]
    print("  href={}".format(href[:100]))
    print("  context=...{}".format(txt_before[-30:]))
    print()

# Print all window.location / redirect scripts
for m in re.finditer(r'window\.location[^;]*;', r.text):
    print("  script: {}".format(m.group()[:120]))

# Check if the actual links work
print("\n--- Testing resolved megaup links ---")
for l in ["https://megaup.net/13Xzt/MLSBD.Shop-The_Batman_(2022)_1337xHD.Shop-Dual_Audio_Hindi_ORG_480p.mkv",
           "https://uptomega.me/9pp2qwjiboqy"]:
    r2 = _cffi_session.get(l, impersonate="chrome", timeout=10, allow_redirects=True)
    print("\n{}:".format(l[:60]))
    print("  Status={}, URL={}, len={}".format(r2.status_code, r2.url[:80], len(r2.text)))
    if r2.status_code == 200:
        # look for download links
        for m in re.finditer(r'href="(https?://[^"]*(?:\.mkv|\.mp4|download)[^"]*)"', r2.text):
            print("    link: {}".format(m.group(1)[:100]))
        for m in re.finditer(r'src="(https?://[^"]*(?:\.mkv|\.mp4))"', r2.text):
            print("    src: {}".format(m.group(1)[:100]))
