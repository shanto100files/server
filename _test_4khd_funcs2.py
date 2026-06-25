import urllib.request, zipfile, json, io, re

r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/skystream-plugins/main/dist/dev.akash.stars.4khd.sky", timeout=15)
z = zipfile.ZipFile(io.BytesIO(r.read()))
js = z.read("plugin.js").decode("utf-8", errors="replace")

# Find function definitions
for name in ["async function kt", "async function Lt", "async function Ut", "async function Mt", "async function As", "let As", "const As"]:
    idx = js.find(name)
    if idx >= 0:
        print("=== {} (at {}) ===".format(name, idx))
        # Print up to 2000 chars
        print(js[idx:idx+2000])
        print()
