import urllib.request, json

r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/skystream-plugins/main/repo.json", timeout=15)
data = json.loads(r.read().decode())

for pl in data.get("pluginLists", []):
    print("pluginList URL: {}".format(pl[:120]))
    r2 = urllib.request.urlopen(pl, timeout=15)
    pl_data = json.loads(r2.read().decode())
    if isinstance(pl_data, list):
        print("  plugins: {}".format(len(pl_data)))
        for p in pl_data[:20]:
            if isinstance(p, dict):
                name = p.get("name","")
                pkg = p.get("packageName","")
                url = p.get("fileUrl","") or p.get("url","") or p.get("manifest","")
                print("    {} | {} | {}".format(name, pkg, str(url)[:100]))
    elif isinstance(pl_data, dict):
        print("  Keys: {}".format(list(pl_data.keys())[:10]))
