import urllib.request, json

r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/skystream-plugins/main/repo.json", timeout=15)
data = json.loads(r.read().decode())
print(type(data).__name__)
if isinstance(data, dict):
    for k, v in data.items():
        print("{}: {}".format(k, type(v).__name__))
        if isinstance(v, list):
            print("  count: {}".format(len(v)))
            for item in v[:5]:
                if isinstance(item, dict):
                    print("  name={} id={} version={}".format(item.get("name",""), item.get("id",""), item.get("version","")))
                    manif = item.get("manifest", "")
                    print("    manifest: {}".format(str(manif)[:150]))
elif isinstance(data, list):
    print("count: {}".format(len(data)))
    for item in data[:5]:
        if isinstance(item, dict):
            print("  name={}".format(item.get("name","")))
