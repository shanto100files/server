import urllib.request, zipfile, json, io, re

r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/skystream-plugins/main/dist/dev.akash.stars.4khd.sky", timeout=15)
z = zipfile.ZipFile(io.BytesIO(r.read()))
js = z.read("plugin.js").decode("utf-8", errors="replace")

# Find the key functions
for name in ["getHome", "search", "load", "loadStreams"]:
    m = re.search(r"(globalThis\." + name + r"\s*=\s*[^;]+)", js)
    if m:
        print("=== {} ===".format(name))
        print(m.group(1)[:500])
        print()
