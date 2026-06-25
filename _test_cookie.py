import urllib.request, json

repos = [
    "https://raw.githubusercontent.com/akashdh11/skystream-plugins/main/repo.json",
    "https://raw.githubusercontent.com/NivinCNC/CNCVerse-Sky-Stream-Extension/main/repo.json",
    "https://raw.githubusercontent.com/likhithkrishna1103-tech/Hindmovie/main/repo.json",
]

# Check each repo for the cookie plugins
for repo_url in repos:
    try:
        r2 = urllib.request.urlopen(repo_url, timeout=15)
        repo_data = json.loads(r2.read().decode())
        name = repo_data.get("name", "")
        for pl_url in repo_data.get("pluginLists", []):
            try:
                r3 = urllib.request.urlopen(pl_url, timeout=15)
                data_raw = r3.read().decode("utf-8", errors="replace")
                if "cookie" in data_raw.lower() or "vegamovies" in data_raw.lower():
                    print("Found in repo: {}".format(name))
                    print("  URL: {}".format(pl_url))
                    plugins = json.loads(data_raw)
                    for p in plugins if isinstance(plugins, list) else []:
                        pname = p.get("name","")
                        if "vega" in pname.lower() or "cookie" in str(p.get("packageName","")).lower():
                            print("  {} | {} | {}".format(pname, p.get("packageName",""), p.get("fileUrl","") or p.get("manifest","")))
            except:
                pass
    except:
        pass
