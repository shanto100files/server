import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import _cffi_session
from bs4 import BeautifulSoup
import re

url = "https://fast-dl.one/dl/3f297d"
r = _cffi_session.get(url, impersonate="chrome", timeout=15, allow_redirects=True)
soup = BeautifulSoup(r.text, "lxml")

# Print all scripts content
for script in soup.find_all("script"):
    if script.string:
        for m in re.finditer(r'(https?://[^""\s<>]+(?:\.mkv|\.mp4|download|file)[^""\s<>]*)', script.string):
            print("Script URL: {}".format(m.group()[:120]))

# Iframes
for iframe in soup.find_all("iframe"):
    print("Iframe src: {}".format(iframe.get("src","")[:100]))

# Forms
for form in soup.find_all("form"):
    print("Form: action={}".format(form.get("action","")[:100]))
    for inp in form.find_all("input"):
        nm = inp.get("name","")
        vl = inp.get("value","")
        if nm or vl:
            print("  {} = {}".format(nm, str(vl)[:60]))

# data attributes
for attr in ["data-src", "data-url", "data-link", "data-file", "data-download"]:
    for el in soup.find_all(attrs={attr: True}):
        print("{} = {}".format(attr, el[attr][:100]))

# Check meta refresh / redirect
for meta in soup.find_all("meta"):
    if meta.get("http-equiv","").lower() == "refresh":
        print("Meta refresh: {}".format(meta.get("content","")))
