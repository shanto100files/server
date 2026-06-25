import sys, time, re, base64
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get

vcloud_url = "https://vcloud.zip/vyjyrddiwcsyuy1"
t0 = time.time()
vcloud_html = cf_get(vcloud_url, timeout=15)
print("Step 4 vcloud: {} bytes in {:.1f}s".format(len(vcloud_html) if vcloud_html else 0, time.time()-t0))

if vcloud_html:
    m = re.search(r'var\s+url\s*=\s*atob\(atob\(["\']([^"\']+)["\']\)\)', vcloud_html)
    if m:
        b64 = m.group(1)
        while len(b64) % 4 != 0: b64 += "="
        once = base64.b64decode(b64).decode()
        while len(once) % 4 != 0: once += "="
        token_url = base64.b64decode(once).decode()
        print("Token URL: {}".format(token_url))
        
        # Step 5: Fetch token page
        t1 = time.time()
        token_html = cf_get(token_url, timeout=15)
        print("Step 5 Token page: {} bytes in {:.1f}s".format(len(token_html) if token_html else 0, time.time()-t1))
        
        if token_html:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(token_html, "lxml")
            for h2 in soup.find_all("h2"):
                for a in h2.find_all_next("a", href=True):
                    h = a["href"]
                    t = a.get_text(strip=True)
                    if h.startswith("http") and not any(x in h for x in [".css", ".js", "fonts", "favicon"]):
                        print("  link: {} | text={}".format(h[:100], t[:50]))
    else:
        print("No double-base64 pattern found")
        print(vcloud_html[-500:])
