import re, json
from bs4 import BeautifulSoup
from client import http_get

def resolve_hubdrive(url: str) -> list[dict]:
    """HubDrive → HubCloud → gamerxyt → direct download links"""
    sources = []

    try:
        from curl_cffi import requests as cffi_requests
        r = cffi_requests.get(url, impersonate="chrome", timeout=15)
        html = r.text if r.status_code == 200 else None
    except:
        html = None

    if not html:
        return sources

    soup = BeautifulSoup(html, "html.parser")
    meta = {}

    title_el = soup.select_one("h6.m-0, .card-header h6, title")
    if title_el:
        meta["title"] = title_el.get_text(strip=True).replace("HubDrive | ", "")
        q_match = re.search(r'(2160p|1080p|720p|480p|4K)', meta["title"], re.IGNORECASE)
        if q_match:
            meta["quality"] = q_match.group(1)

    for td in soup.select("td"):
        if "File Size" in td.get_text():
            next_td = td.find_next_sibling("td")
            if next_td:
                meta["fileSize"] = next_td.get_text(strip=True)

    m = re.search(r'id="down-id"[^>]*>(\d+)<', html)
    if m:
        file_id = m.group(1).strip()
        try:
            session = cffi_requests.Session(impersonate="chrome")
            session.get(url, timeout=15)
            r2 = session.post(
                "https://hubdrive.space/ajax.php?ajax=download",
                data={"id": file_id},
                headers={
                    "Referer": url,
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=15
            )
            if r2.text:
                try:
                    resp = r2.json()
                    if resp.get("code") == "200" and resp.get("data"):
                        dl_data = resp["data"]
                        if isinstance(dl_data, str):
                            dl_url = dl_data
                        elif isinstance(dl_data, dict):
                            dl_url = dl_data.get("url") or dl_data.get("link") or dl_data.get("download_url", "")
                        else:
                            dl_url = str(dl_data)
                        if dl_url and dl_url.startswith("http"):
                            fmt = "mkv"
                            if ".mp4" in dl_url.lower():
                                fmt = "mp4"
                            sources.append({
                                "url": dl_url,
                                "quality": meta.get("quality", "HD"),
                                "provider": "HDHub4U",
                                "format": fmt,
                                "fileSize": meta.get("fileSize", ""),
                                "filename": meta.get("title", ""),
                            })
                            return sources
                except:
                    pass
        except:
            pass

    hubcloud_link = None
    for a in soup.select("a[href*='hubcloud']"):
        href = a.get("href", "")
        if "/drive/" in href:
            hubcloud_link = href
            break

    if not hubcloud_link:
        return sources

    try:
        from curl_cffi import requests as cffi_requests2
        hc_resp = cffi_requests2.get(hubcloud_link, impersonate="chrome", timeout=15)
        hc_html = hc_resp.text if hc_resp.status_code == 200 else None
    except:
        hc_html = None

    if not hc_html:
        return sources

    hc_soup = BeautifulSoup(hc_html, "html.parser")
    gamerxyt_link = None
    for a in hc_soup.select("a[href*='gamerxyt']"):
        href = a.get("href", "")
        if "hubcloud.php" in href:
            gamerxyt_link = href
            break

    if not gamerxyt_link:
        dl_div = hc_soup.select_one(".vd")
        if dl_div:
            a_tag = dl_div.select_one("a[href]")
            if a_tag:
                gamerxyt_link = a_tag.get("href", "")

    if not gamerxyt_link:
        return sources

    try:
        from curl_cffi import requests as cffi_requests3
        gx_resp = cffi_requests3.get(gamerxyt_link, impersonate="chrome", timeout=20)
        gx_html = gx_resp.text if gx_resp.status_code == 200 else None
    except:
        gx_html = None

    if not gx_html:
        return sources

    gx_soup = BeautifulSoup(gx_html, "html.parser")

    seen = set()
    for a in gx_soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True).lower()

        if not href.startswith("http"):
            continue
        if any(x in href for x in ["google.com", "t.me", "snvhost", "bonuscaf", "facebook", "twitter"]):
            continue
        if any(x in text for x in ["copy", "telegram", "how to", "tutorial", "refresh", "report"]):
            continue
        is_cdn = any(x in href for x in ["cdn.fsl-buckets", "gpdl.hubcloud", "files.dolic45578", "workers.dev", "cdn.fukggl", "cdn.sndcdn", "cdn.discord"])
        is_direct = bool(re.search(r'\.(mkv|mp4|m3u8|mpd)(?:\?|$)', href, re.IGNORECASE))
        if is_cdn or is_direct:
            if href not in seen:
                seen.add(href)
                fmt = "mkv"
                if ".mp4" in href.lower():
                    fmt = "mp4"

                server = "Unknown"
                if "fsl-buckets" in href:
                    server = "FSLv2"
                elif "gpdl.hubcloud" in href:
                    server = "10Gbps"
                elif "dolic45578" in href or "workers.dev" in href:
                    server = "Workers"
                elif "fukggl" in href:
                    server = "CDN"

                sources.append({
                    "url": href,
                    "quality": meta.get("quality", "HD"),
                    "provider": f"HubCloud ({server})",
                    "format": fmt,
                    "fileSize": meta.get("fileSize", ""),
                    "filename": meta.get("title", ""),
                })

    return sources
