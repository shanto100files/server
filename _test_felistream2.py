import urllib.request, json

r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/sky-universe/refs/heads/main/mega_repo.json", timeout=15)
mega = json.loads(r.read().decode())
repo_url = mega["repos"][4]

r2 = urllib.request.urlopen(repo_url, timeout=15)
repo_data = json.loads(r2.read().decode())

lines = ["Name: " + repo_data.get("name","")]
for pl_url in repo_data.get("pluginLists", []):
    lines.append("PL: " + pl_url)
    try:
        r3 = urllib.request.urlopen(pl_url, timeout=15)
        plugins = json.loads(r3.read().decode("utf-8", errors="replace"))
        for p in plugins if isinstance(plugins, list) else []:
            pname = p.get("name","")
            pkg = p.get("packageName","")
            furl = p.get("fileUrl","") or p.get("manifest","") or ""
            lines.append("  {} | {} | {}".format(pname, pkg, furl[:120]))
    except Exception as e:
        lines.append("  Error: " + str(e)[:60])

with open(r"E:\cinepix\termux-server\_felistream_plugins.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("Done, {} lines".format(len(lines)))
