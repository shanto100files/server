"""
HubCloud extractor — resolves hubcloud URLs to direct download links.
FSL Server, Pixeldrain, S3, FSLv2, BuzzServer, Mega Server, Gofile, gpdl2.
"""
import re
from bs4 import BeautifulSoup
from client import cf_get, http_get
from urllib.parse import urlparse, parse_qs

HUBCLOUD_DOMAINS = ["https://hubcloud.foo", "https://hubcloud.one", "https://hubcloud.art"]


def _get_base_url(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def extract_hubcloud(url: str, quality: str = "", referer: str = "") -> list[dict]:
    results = []
    base_url = _get_base_url(url)
    headers = {"Referer": referer or base_url}

    try:
        download_url = url

        if "hubcloud.php" not in url:
            page_html = cf_get(url, headers=headers, timeout=15)
            if not page_html:
                page_html_obj = http_get(url, headers=headers, timeout=15)
                if page_html_obj:
                    page_html = page_html_obj.text
            if not page_html:
                return results

            soup = BeautifulSoup(page_html, "html.parser")

            dl_el = soup.select_one("#download")
            if dl_el and dl_el.get("href"):
                href = dl_el["href"]
                download_url = href if href.startswith("http") else f"{base_url}{href}"
            else:
                php_link = soup.select_one('a[href*="hubcloud.php"]')
                if php_link:
                    href = php_link.get("href", "")
                    download_url = href if href.startswith("http") else f"{base_url}{href}"
                else:
                    btn = soup.select_one("a.btn-primary")
                    if btn:
                        href = btn.get("href", "")
                        download_url = href if href.startswith("http") else f"{base_url}{href}"

        resp_html = cf_get(download_url, headers={"Referer": url}, timeout=15)
        if not resp_html:
            r = http_get(download_url, headers={"Referer": url}, timeout=15)
            if r:
                resp_html = r.text
        if not resp_html:
            return results

        soup = BeautifulSoup(resp_html, "html.parser")

        file_size = ""
        size_el = soup.select_one("i#size")
        if size_el:
            file_size = size_el.get_text(strip=True)

        header_el = soup.select_one(".card-header, h3, h4")
        header_text = header_el.get_text(strip=True) if header_el else ""
        detected_quality = quality or _extract_quality(header_text)

        for a in soup.select("a.btn, a.btn-primary, a.btn-danger, a.btn-success, a.btn-warning"):
            href = a.get("href", "")
            text = a.get_text(strip=True).lower()
            if not href:
                continue
            if href.startswith("#") or "javascript:" in href:
                continue

            if "fsl server" in text:
                results.append({
                    "url": href,
                    "quality": detected_quality,
                    "provider": "HubCloud",
                    "format": "mkv",
                    "fileSize": file_size,
                    "server": "FSL Server",
                })
            elif "download file" in text or "10gbps" in text:
                direct = _resolve_gpdl2(href)
                results.append({
                    "url": direct or href,
                    "quality": detected_quality,
                    "provider": "HubCloud",
                    "format": "mkv",
                    "fileSize": file_size,
                    "server": "10Gbps",
                })
            elif "pixeldra" in text or "pixel" in text:
                final = href
                if "/api/file/" not in href:
                    parts = href.rstrip("/").split("/")
                    final = f"{_get_base_url(href)}/api/file/{parts[-1]}?download"
                results.append({
                    "url": final,
                    "quality": detected_quality,
                    "provider": "HubCloud",
                    "format": "mkv",
                    "fileSize": file_size,
                    "server": "Pixeldrain",
                })
            elif "s3 server" in text:
                results.append({
                    "url": href,
                    "quality": detected_quality,
                    "provider": "HubCloud",
                    "format": "mkv",
                    "fileSize": file_size,
                    "server": "S3 Server",
                })
            elif "fslv2" in text:
                results.append({
                    "url": href,
                    "quality": detected_quality,
                    "provider": "HubCloud",
                    "format": "mkv",
                    "fileSize": file_size,
                    "server": "FSLv2",
                })
            elif "buzzserver" in text:
                buzz = _extract_buzz(href)
                if buzz:
                    results.append({
                        "url": buzz,
                        "quality": detected_quality,
                        "provider": "HubCloud",
                        "format": "mkv",
                        "fileSize": file_size,
                        "server": "BuzzServer",
                    })
            elif "mega server" in text:
                results.append({
                    "url": href,
                    "quality": detected_quality,
                    "provider": "HubCloud",
                    "format": "mkv",
                    "fileSize": file_size,
                    "server": "Mega Server",
                })
            elif "gofile" in text or "gofile" in href:
                results.append({
                    "url": href,
                    "quality": detected_quality,
                    "provider": "HubCloud",
                    "format": "mkv",
                    "fileSize": file_size,
                    "server": "Gofile",
                })
            elif "telegram" in text:
                results.append({
                    "url": href,
                    "quality": detected_quality,
                    "provider": "HubCloud",
                    "format": "mkv",
                    "fileSize": file_size,
                    "server": "Telegram",
                })
            elif "copy" not in text and "open" not in text:
                results.append({
                    "url": href,
                    "quality": detected_quality,
                    "provider": "HubCloud",
                    "format": "mkv",
                    "fileSize": file_size,
                    "server": "Direct",
                })

    except Exception as e:
        pass

    return results


def _extract_buzz(url: str) -> str | None:
    try:
        dl_url = url.rstrip("/") + "/download" if "/download" not in url else url
        r = http_get(dl_url, headers={"Referer": url}, timeout=10)
        if r:
            for key in ["hx-redirect", "HX-Redirect"]:
                redir = r.headers.get(key)
                if redir:
                    return redir
            loc = r.headers.get("location")
            if loc:
                return loc
    except:
        pass
    return None


def _extract_quality(text: str) -> str:
    m = re.search(r"(\d{3,4})p", text, re.IGNORECASE)
    return f"{m.group(1)}p" if m else "1080p"


def _resolve_gpdl2(url: str) -> str | None:
    try:
        from curl_cffi import requests as cffi_requests
        r = cffi_requests.get(url, impersonate="chrome", timeout=10, allow_redirects=False)
        loc = r.headers.get("location", "")
        if not loc:
            return None
        r2 = cffi_requests.get(loc, impersonate="chrome", timeout=10, allow_redirects=False, headers={"Referer": url})
        loc2 = r2.headers.get("location", "")
        if "dl.php" in loc2 and "link=" in loc2:
            parsed = urlparse(loc2)
            qs = parse_qs(parsed.query)
            gurl = qs.get("link", [""])[0]
            if gurl:
                return gurl
    except Exception:
        pass
    return None
