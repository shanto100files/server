import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
from bs4 import BeautifulSoup
from providers.auto_resolver import title_matches_search

# Test The Batman search
query = "The Batman"
html = cf_get("https://mlsbd.co/?s=" + query.replace(" ", "+"), timeout=10)
print("Search HTML: {} bytes".format(len(html) if html else 0))
if html:
    soup = BeautifulSoup(html, "lxml")
    found = False
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if "mlsbd.co" in href and href != "https://mlsbd.co/" and "/?s=" not in href:
            # Check if title matches
            match = title_matches_search(text, query)
            if match:
                found = True
                print("  MATCH: {} - {}".format(href, text[:60]))
            elif query.split()[0].lower() in text.lower():
                print("  PARTIAL: {} - {}".format(href, text[:60]))
    
    if not found:
        print("  NO MATCHES found. Checking all links with 'batman':")
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if "batman" in text.lower() or "batman" in href.lower():
                print("    href={}  text={}".format(href, text[:60]))
