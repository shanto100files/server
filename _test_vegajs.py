import urllib.request, zipfile, json, io

r = urllib.request.urlopen("https://raw.githubusercontent.com/thegnsme/skystream-plugins/repo/dist/com.cookie.vegamovies.sky", timeout=15)
z = zipfile.ZipFile(io.BytesIO(r.read()))

# Read plugin.json
pjson = json.loads(z.read("plugin.json").decode())
print("=== plugin.json ===")
print(json.dumps(pjson, indent=2))

# Read plugin.js
js = z.read("plugin.js").decode("utf-8", errors="replace")
print("\n=== plugin.js ===")
print(js)
