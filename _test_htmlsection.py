with open(r"E:\cinepix\termux-server\_hubcloud_analysis.html", "r", encoding="utf-8") as f:
    html = f.read()

idx = html.find("10Gbps")
if idx >= 0:
    start = max(0, idx - 300)
    end = min(len(html), idx + 500)
    print(html[start:end])
