import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
import re

# Check post page for ALL download-type links
post_html = cf_get("https://mlsbd.co/the-batman-2022-dual-audio-hindi-english-web-dl-480p-720p-1080p-x264-550mb-1-4gb-1-9gb-14-5gb-esub-download-watch-online/")
soup = BeautifulSoup(post_html, "lxml")

# Check for streamable links
print("Direct streamable links:")
for a in soup.select("a[href]"):
    href = a.get("href", "")
    if any(x in href for x in ["gdflix", "r2.dev", "pixeldrain", "drive.google", "blob.core", "mega.nz", "bonghd"]):
        print("  {}".format(href[:80]))

# Check for gdflix specifically in full text
if "gdflix" in post_html:
    gd_links = re.findall(r'https?://[^"\s<>]*gdflix[^"\s<>]*', post_html)
    print("\ngdflix links in page: {}".format(len(gd_links)))
    for l in gd_links[:5]:
        print("  {}".format(l[:80]))
