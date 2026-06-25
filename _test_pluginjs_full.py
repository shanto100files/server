import urllib.request, zipfile, json, io

r = urllib.request.urlopen("https://raw.githubusercontent.com/akashdh11/skystream-plugins/main/dist/dev.akash.stars.bollyflix.sky", timeout=15)
z = zipfile.ZipFile(io.BytesIO(r.read()))
js = z.read("plugin.js").decode("utf-8", errors="replace")
print(js)
