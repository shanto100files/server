import urllib.request, zipfile, json, io

r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/skystream-plugins/main/dist/dev.akash.stars.bollyflix.sky", timeout=15)
data = r.read()

z = zipfile.ZipFile(io.BytesIO(data))
print("Files in ZIP: {}".format(z.namelist()))

for name in z.namelist():
    content = z.read(name).decode("utf-8", errors="replace")
    print("\n=== {} ===".format(name))
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                if isinstance(v, str) and len(v) > 200:
                    print("  {}: {}...".format(k, v[:200]))
                elif isinstance(v, list):
                    print("  {}: list[{}]".format(k, len(v)))
                    for item in v[:3]:
                        if isinstance(item, dict):
                            print("    {}".format(json.dumps(item, indent=2)[:200]))
                        else:
                            print("    {}".format(str(item)[:150]))
                else:
                    print("  {}: {}".format(k, str(v)[:150]))
        else:
            print(content[:500])
    except:
        print(content[:500])
