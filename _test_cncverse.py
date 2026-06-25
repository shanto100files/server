import urllib.request, json, zipfile, io

# Check CNCVerse repo
r = urllib.request.urlopen("https://raw.githubusercontent.com/NivinCNC/CNCVerse-Sky-Stream-Extension/main/repo.json", timeout=15)
data = json.loads(r.read().decode())
print(json.dumps(data, indent=2)[:2000])
