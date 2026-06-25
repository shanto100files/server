import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get, _cffi_session
import re, time

url = "https://megaup.net/13Xzt/MLSBD.Shop-The_Batman_(2022)_1337xHD.Shop-Dual_Audio_Hindi_ORG_480p.mkv"

t0 = time.time()
html = cf_get(url, timeout=15)
print("cf_get: {} bytes in {:.1f}s".format(len(html) if html else 0, time.time() - t0))

if html:
    # Check for direct links
    for pat in [r'https?://[^""\s<>]*(?:\.mkv|\.mp4|\.avi|download)[^""\s<>]*',
                r'"(https?://[^""]*(?:\.mkv|\.mp4)[^""]*)"',
                r"'(https?://[^']*(?:\.mkv|\.mp4)[^']*)'",
                r'<a[^>]*href="([^"]*\.(?:mkv|mp4))[^"]*"',
                r'<a[^>]*href="([^"]*download[^"]*)"',
                r'iframe[^>]*src="([^"]*)"',
                r'src="(https?://[^"]*)"']:
        found = re.findall(pat, html, re.IGNORECASE)
        if found:
            for f in found[:5]:
                print("  {}: {}".format(pat.split("{")[0][:30], f[:100]))

# Try cffi approach
t0 = time.time()
r = _cffi_session.get(url, impersonate="chrome", timeout=15, allow_redirects=True)
print("\ncffi: Status={}, URL={}, {} bytes in {:.1f}s".format(r.status_code, r.url[:80], len(r.text), time.time() - t0))

if r.text:
    for pat in [r'https?://[^""\s<>]*(?:\.mkv|\.mp4|\.avi|download)[^""\s<>]*',
                r'"(https?://[^""]*(?:\.mkv|\.mp4)[^""]*)"']:
        found = re.findall(pat, r.text, re.IGNORECASE)
        if found:
            for f in found[:5]:
                print("  {}: {}".format(pat[:30], f[:100]))

# Check if mkvs are directly accessible
import urllib.request
req = urllib.request.Request("https://megaup.net/13Xzt/MLSBD.Shop-The_Batman_(2022)_1337xHD.Shop-Dual_Audio_Hindi_ORG_480p.mkv", method="HEAD")
try:
    resp = urllib.request.urlopen(req, timeout=10)
    print("\nHEAD on file: Status={}, Content-Type={}".format(resp.status, resp.headers.get("Content-Type")))
except Exception as e:
    print("\nHEAD on file failed: {}".format(e))
