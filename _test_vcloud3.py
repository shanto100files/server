import sys
sys.path.insert(0, r"E:\cinepix\termux-server")
from client import cf_get
import re, json

r = cf_get("https://vcloud.zip/vyjyrddiwcsyuy1", timeout=15)

# Find all script contents
for m in re.finditer(r'<script[^>]*>([\s\S]*?)</script>', r):
    script = m.group(1).strip()
    if len(script) > 20 and "var " in script:
        # Check for URLs
        for u in re.finditer(r'(https?://[^""\s\'<>]+(?:fastdl|hubcloud|vcloud|nexdrive|\.mp4|\.mkv)[^""\s\'<>]*)', script):
            print("URL in script: {}".format(u.group()[:100]))
        # Check for JSON
        for j in re.finditer(r'(\{.*"url".*"file".*\})', script):
            try:
                d = json.loads(j.group())
                print("JSON: {}".format(json.dumps(d)[:200]))
            except:
                pass

# Check for inline JSON in HTML
for m in re.finditer(r'(?:\{|\{)[^{}]*"url"[^{}]*(?:\}|\})', r):
    try:
        d = json.loads("{" + m.group() + "}")
        print("JSON obj: {}".format(str(d)[:200]))
    except:
        pass

# Look for specific patterns the plugin finds
for pat in [r'var\s+reurl\s*=\s*"([^"]+)"',
            r'var\s+pxl\s*=\s*["\']([^"\']+)["\']',
            r'hx-redirect\s*=\s*"([^"]+)"',
            r'class="[^"]*btn[^"]*"',
            r'fsl|FSL|Fsl',
            r'10gbps|10Gbps|10 gbps',
            r'BuzzServer|Buzz Server',
            r'Mega Server',
            r'Pixeldrain|PixelServer',
            r'hubcloud\.cx',
            r'fastdl\.zip',
            r'vcloud\.zip',
            r'download'][^=]*=[^"]*"([^"]+)"']:
    for m in re.finditer(pat, r, re.IGNORECASE):
        print("Pattern {}: {}".format(m.re.pattern[:30], m.group()[:120]))
