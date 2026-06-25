import urllib.request, json

# Check remaining repos from mega_repo.json
r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/sky-universe/refs/heads/main/mega_repo.json", timeout=15)
data = json.loads(r.read().decode())
repos = data.get("repos", [])
print("Total repos: {}".format(len(repos)))

for repo_url in repos:
    try:
        r2 = urllib.request.urlopen(repo_url, timeout=15)
        repo_data = json.loads(r2.read().decode())
        name = repo_data.get("name", "")
        plugin_lists = repo_data.get("pluginLists", [])
        print("\nRepo: {}".format(name))
        for pl_url in plugin_lists:
            try:
                r3 = urllib.request.urlopen(pl_url, timeout=15)
                plugins = json.loads(r3.read().decode())
                if isinstance(plugins, list):
                    for p in plugins:
                        pname = p.get("name","")
                        if "vega" in pname.lower():
                            print("  VEGA FOUND: {}".format(pname))
                            print("    package: {}".format(p.get("packageName","")))
                            print("    url: {}".format(p.get("fileUrl","") or p.get("manifest","")))
            except Exception as e:
                print("  pl error: {} | {}".format(type(e).__name__, str(e)[:50]))
    except Exception as e:
        print("{}: {}".format(type(e).__name__, str(e)[:50]))
