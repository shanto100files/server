import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from bs4 import BeautifulSoup

with open(r"E:\cinepix\termux-server\_hubcloud_analysis.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")
body = soup.find("body")

results = []
for a in body.find_all("a", href=True):
    h = a["href"]
    t = a.get_text(strip=True)
    if h.startswith("http") and not any(x in h for x in [".css", ".js", "cdn.", "fonts", "unpkg", "use.fontawesome", "favicon"]):
        clean_t = t.encode("ascii", "ignore").decode().strip()
        results.append("{} | {}".format(h[:100], clean_t[:50]))

print("Total links: {}".format(len(results)))
for r in results:
    print("  " + r)
