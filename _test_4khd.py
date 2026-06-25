import urllib.request, zipfile, json, io

# Download 4K HD plugin from Stars repo
r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/skystream-plugins/main/dist/dev.akash.stars.4khd.sky", timeout=15)
z = zipfile.ZipFile(io.BytesIO(r.read()))

pjson = json.loads(z.read("plugin.json").decode())
print("=== plugin.json ===")
print(json.dumps(pjson, indent=2))

js = z.read("plugin.js").decode("utf-8", errors="replace")
print("\n=== plugin.js (first 3000 chars) ===")
print(js[:3000])
