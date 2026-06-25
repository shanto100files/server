import urllib.request, zipfile, json, io

r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/skystream-plugins/main/dist/dev.akash.stars.4khd.sky", timeout=15)
z = zipfile.ZipFile(io.BytesIO(r.read()))
js = z.read("plugin.js").decode("utf-8", errors="replace")

# Print the complete functions
for name in ["async function Ft", "async function Ht", "function Bt", "async function Nt", "function W", "function qt"]:
    idx = js.find(name)
    if idx >= 0:
        end = js.find("\n\n", idx)
        if end == -1: end = idx + 1500
        print("=== {} ===".format(name))
        print(js[idx:end])
        print()
