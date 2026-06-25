import urllib.request, json

r = urllib.request.urlopen("https://raw.githubusercontent.com/likhithkrishna1103-tech/Hindmovie/main/dist/plugins.json", timeout=15)
data = json.loads(r.read().decode())
lines = []
for item in data[:30]:
    name = item.get("name","")
    pkg = item.get("packageName","")
    url = item.get("fileUrl","") or item.get("manifest","") or ""
    lines.append("|".join([name, pkg, url[:80]]))
with open(r"E:\cinepix\termux-server\_hindmovie_plugins.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("Done, {} plugins".format(len(lines)))
