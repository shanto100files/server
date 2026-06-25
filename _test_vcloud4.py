import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
import re, json

r = cf_get("https://vcloud.zip/vyjyrddiwcsyuy1", timeout=15)

# Find all script contents
for m in re.finditer(r"<script[^>]*>([\s\S]*?)</script>", r):
    script = m.group(1).strip()
    if len(script) > 50:
        # Check for URLs in scripts
        for u in re.finditer(r"https?://[^\"\s\'<>]+(?:fastdl|hubcloud|vcloud|download|\.mp4|\.mkv)[^\"\s\'<>]*", script):
            print("URL: {}".format(u.group()[:100]))
        # Check for var assignments
        for v in re.finditer(r'var\s+(\w+)\s*=\s*["\']([^"\']+)["\']', script):
            print("Var: {} = {}".format(v.group(1), v.group(2)[:80]))

# Check for hx-redirect
for m in re.finditer(r'hx-redirect\s*=\s*"([^"]+)"', r):
    print("hx-redirect: {}".format(m.group(1)[:100]))

# Check for FSL references anywhere
for m in re.finditer(r'[Ff][Ss][Ll]', r):
    start = max(0, m.start()-50)
    end = min(len(r), m.end()+50)
    print("FSL context: ...{}...".format(r[start:end].strip()))
    break

# Check raw HTML surrounding download-related keywords
for kw in ["btn", "dwd", "download", "link", "url"]:
    for m in re.finditer(kw, r, re.IGNORECASE):
        start = max(0, m.start()-30)
        end = min(len(r), m.end()+60)
        ctx = r[start:end].strip()
        if "css" not in ctx and "font" not in ctx:
            print("  {}: ...{}...".format(kw, ctx[:100]))
