import urllib.request, json

r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/sky-universe/refs/heads/main/mega_repo.json", timeout=15)
mega = json.loads(r.read().decode())
repos = mega.get("repos", [])

# Repo 5 is feliStream
repo_url = repos[4]  # 0-indexed
print("Repo URL: {}".format(repo_url))

r2 = urllib.request.urlopen(repo_url, timeout=15)
repo_data = json.loads(r2.read().decode())
print("Name: {}".format(repo_data.get("name","")))

for pl_url in repo_data.get("pluginLists", []):
    print("PL: {}".format(pl_url))
    r3 = urllib.request.urlopen(pl_url, timeout=15)
    raw = r3.read().decode("utf-8", errors="replace")
    plugins = json.loads(raw)
    for p in plugins if isinstance(plugins, list) else []:
        pname = p.get("name","")
        pkg = p.get("packageName","")
        furl = p.get("fileUrl","") or ""
        print("  {} | {} | {}".format(pname, pkg, furl[:100]))
