import urllib.request, json

r = urllib.request.urlopen("https://raw.githubusercontent.com/SaurabhKaperwan/Utils/refs/heads/main/urls.json", timeout=15)
data = json.loads(r.read().decode())
print(json.dumps(data, indent=2))
