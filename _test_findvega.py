import urllib.request, json

r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/sky-universe/refs/heads/main/mega_repo.json", timeout=15)
mega = json.loads(r.read().decode())
repos = mega.get("repos", [])

index = 0
for repo_url in repos:
    index += 1
    try:
        r2 = urllib.request.urlopen(repo_url, timeout=15)
        repo_data = json.loads(r2.read().decode())
        name = repo_data.get("name", "")
        plugin_lists = repo_data.get("pluginLists", [])
        for pl_url in plugin_lists:
            try:
                r3 = urllib.request.urlopen(pl_url, timeout=15)
                raw = r3.read()
                try:
                    plugins = json.loads(raw.decode("utf-8"))
                except:
                    plugins = json.loads(raw.decode("utf-8", errors="replace"))
                if isinstance(plugins, list):
                    for p in plugins:
                        if "vega" in p.get("name","").lower() or "vega" in p.get("packageName","").lower():
                            print("REPO {}: {} | {} | {}".format(index, p.get("name",""), p.get("packageName",""), p.get("fileUrl","") or p.get("manifest","")))
            except Exception as e:
                pass
    except Exception as e:
        print("REPO {} ERROR: {}".format(index, str(e)[:60]))
