import urllib.request, json

r = urllib.request.urlopen("https://raw.githubusercontent.com/thegnsme/skystream-plugins/repo/dist/plugins.json", timeout=15)
plugins = json.loads(r.read().decode())

for p in plugins:
    if "vega" in p.get("name","").lower():
        print(json.dumps(p, indent=2))
        break
