import urllib.request, json

r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/sky-universe/refs/heads/main/mega_repo.json", timeout=15)
data = json.loads(r.read().decode())

results = []
for repo_url in data.get("repos", []):
    try:
        r2 = urllib.request.urlopen(repo_url, timeout=15)
        repo_data = json.loads(r2.read().decode())
        name = repo_data.get("name", "")
        for pl_url in repo_data.get("pluginLists", []):
            try:
                r3 = urllib.request.urlopen(pl_url, timeout=15)
                plugins = json.loads(r3.read().decode())
                if isinstance(plugins, list):
                    for p in plugins:
                        pname = p.get("name","")
                        pkg = p.get("packageName","")
                        furl = p.get("fileUrl","") or p.get("manifest","") or ""
                        results.append("{} | {} | {}".format(pname, pkg, furl))
            except:
                pass
    except:
        pass

with open(r"E:\cinepix\termux-server\_allplugins.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("Total plugins found: {}".format(len(results)))
