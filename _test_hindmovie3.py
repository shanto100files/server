import urllib.request, json, sys

r = urllib.request.urlopen("https://raw.githubusercontent.com/likhithkrishna1103-tech/Hindmovie/main/dist/plugins.json", timeout=15)
data = json.loads(r.read().decode())
for item in data[:30]:
    name = item.get("name","")
    pkg = item.get("packageName","")
    url = item.get("fileUrl","") or item.get("manifest","") or ""
    try:
        print("{} | {} | {}".format(name, pkg, url[:80]))
    except:
        print("{!r} | {} | {}".format(name, pkg, url[:80]))
