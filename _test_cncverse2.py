import urllib.request, json

r = urllib.request.urlopen("https://raw.githubusercontent.com/NivinCNC/CNCVerse-Sky-Stream-Extension/main/dist/plugins.json", timeout=15)
data = json.loads(r.read().decode())
for item in data:
    print("{} | {} | {}".format(item.get("name",""), item.get("packageName",""), str(item.get("fileUrl",""))[:80]))
