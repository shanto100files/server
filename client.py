"""
Shared HTTP client — OPTIMIZED for Koyeb Free Tier.
Faster keepalive, tuned connection pool, exponential backoff.
"""
import httpx
from curl_cffi import requests as cffi_requests

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

_httpx_client = httpx.Client(
    timeout=httpx.Timeout(10.0),
    limits=httpx.Limits(
        max_connections=60,
        max_keepalive_connections=30,
        keepalive_expiry=60,
    ),
    follow_redirects=True,
    headers={"User-Agent": _UA},
    http2=True,
)

_cffi_session = cffi_requests.Session(impersonate="chrome")


def http_get(url: str, headers: dict = None, timeout: int = 10, retries: int = 2) -> httpx.Response | None:
    for attempt in range(retries):
        try:
            r = _httpx_client.get(url, headers=headers or {}, timeout=timeout)
            if r.status_code == 200:
                return r
        except Exception:
            if attempt < retries - 1:
                import time
                time.sleep(0.15 * (attempt + 1))
    return None


def http_post(url: str, content: str = "", headers: dict = None, timeout: int = 10) -> httpx.Response | None:
    try:
        r = _httpx_client.post(url, content=content, headers=headers or {}, timeout=timeout)
        return r
    except:
        pass
    return None


def cf_get(url: str, headers: dict = None, timeout: int = 10, retries: int = 2) -> str | None:
    for attempt in range(retries):
        try:
            h = {"User-Agent": _UA}
            if headers:
                h.update(headers)
            r = _cffi_session.get(url, headers=h, timeout=timeout)
            if r.status_code == 200:
                return r.text
        except Exception:
            if attempt < retries - 1:
                import time
                time.sleep(0.15 * (attempt + 1))
    return None


def cf_post(url: str, data: str = "", headers: dict = None, timeout: int = 10) -> httpx.Response | None:
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
