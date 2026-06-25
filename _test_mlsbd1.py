import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
from providers.mlsbd import MLSBD_DOMAINS

# Test with a known working movie
html = cf_get("https://mlsbd.co/?s=raakh", timeout=10)
print("Search HTML: {} bytes".format(len(html) if html else 0))
if html:
    soup = BeautifulSoup(html, "lxml")
    print("\nAll domain links:")
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if "mlsbd.co" in href and "/?s=" not in href and href != "https://mlsbd.co/" and href != "https://mlsbd.co":
            print("  href={}  text={}".format(href, text[:50]))
            break  # just show first few

    print("\nJust checking if any link has 'raakh' in text:")
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if "mlsbd.co" in href and "raakh" in text.lower():
            print("  FOUND: {} - {}".format(href, text[:50]))
