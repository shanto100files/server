import urllib.request, json

r = urllib.request.urlopen("https://raw.githubusercontent.com/likhithkrishna1103-tech/Hindmovie/main/repo.json", timeout=15)
data = json.loads(r.read().decode())
print(json.dumps(data, indent=2)[:2000])
