"""
Shared HTTP client — curl_cffi for CF-protected sites, httpx for fast API sites.
RAM-optimized: smaller pools, faster cleanup.
"""
import httpx
from curl_cffi import requests as cffi_requests

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

_httpx_client = httpx.Client(
    timeout=httpx.Timeout(4.0),
    limits=httpx.Limits(
        max_connections=80,
        max_keepalive_connections=30,
        keepalive_expiry=60,
    ),
    follow_redirects=True,
    headers={"User-Agent": _UA},
)

_cffi_session = cffi_requests.Session(impersonate="chrome")

def http_get(url: str, headers: dict = None, timeout: int = 4) -> httpx.Response | None:
    try:
        r = _httpx_client.get(url, headers=headers or {}, timeout=timeout)
        if r.status_code == 200:
            return r
    except:
        pass
    return None

def http_post(url: str, content: str = "", headers: dict = None, timeout: int = 4) -> httpx.Response | None:
    try:
        r = _httpx_client.post(url, content=content, headers=headers or {}, timeout=timeout)
        return r
    except:
        pass
    return None

def cf_get(url: str, headers: dict = None, timeout: int = 5) -> str | None:
    try:
        h = {"User-Agent": _UA}
        if headers:
            h.update(headers)
        r = _cffi_session.get(url, headers=h, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return None

def cf_post(url: str, data: str = "", headers: dict = None, timeout: int = 5) -> httpx.Response | None:
    try:
        h = {"User-Agent": _UA}
        if headers:
            h.update(headers)
        r = _cffi_session.post(url, data=data, headers=h, timeout=timeout)
        return r
    except:
        pass
    return None

def close():
    _httpx_client.close()
    _cffi_session.close()
