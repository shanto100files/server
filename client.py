"""
Shared HTTP client — OPTIMIZED for Koyeb Free Tier.
Faster keepalive, tuned connection pool, exponential backoff.
"""
import httpx
import asyncio
import os
import random
from curl_cffi import requests as cffi_requests

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

_httpx_client = httpx.Client(
    timeout=httpx.Timeout(8.0),
    limits=httpx.Limits(
        max_connections=30,
        max_keepalive_connections=15,
        keepalive_expiry=30,
    ),
    follow_redirects=True,
    headers={"User-Agent": _UA},
    http2=True,
)

_PROXIES = []
_proxy_file = os.path.join(os.path.dirname(__file__), "proxies.txt")
if os.path.exists(_proxy_file):
    with open(_proxy_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                _PROXIES.append({"http": line, "https": line})

_IMPERSONATES = ["chrome110", "chrome116", "chrome120", "edge101", "safari15_3"]

_cffi_sessions = []
_cffi_async_sessions = []

for imp in _IMPERSONATES:
    for proxy in (_PROXIES if _PROXIES else [None]):
        _cffi_sessions.append(cffi_requests.Session(impersonate=imp, proxies=proxy))
        _cffi_async_sessions.append(cffi_requests.AsyncSession(impersonate=imp, proxies=proxy))

def _get_sync_session():
    return random.choice(_cffi_sessions)

def _get_async_session():
    return random.choice(_cffi_async_sessions)


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


def cf_get(url: str, headers: dict = None, timeout: int = 10, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            h = {"User-Agent": _UA}
            if headers:
                h.update(headers)
            r = _get_sync_session().get(url, headers=h, timeout=timeout)
            if r.status_code in (200, 404):
                if r.status_code == 200:
                    return r.text
                return None
            
            if r.status_code in (403, 429) and attempt < retries - 1:
                import time
                time.sleep(1.0 * (attempt + 1))
        except Exception:
            if attempt < retries - 1:
                import time
                time.sleep(1.0 * (attempt + 1))
    return None


def cf_post(url: str, data: str = "", headers: dict = None, timeout: int = 10, retries: int = 2) -> httpx.Response | None:
    for attempt in range(retries):
        try:
            h = {"User-Agent": _UA}
            if headers:
                h.update(headers)
            r = _get_sync_session().post(url, data=data, headers=h, timeout=timeout)
            if r.status_code == 200:
                return r
        except Exception:
            if attempt < retries - 1:
                import time
                time.sleep(1.0 * (attempt + 1))
    return None


async def async_cf_get(url: str, headers: dict = None, timeout: int = 10, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            h = {"User-Agent": _UA}
            if headers:
                h.update(headers)
            r = await _get_async_session().get(url, headers=h, timeout=timeout)
            if r.status_code in (200, 404):
                if r.status_code == 200:
                    return r.text
                return None

            if r.status_code in (403, 429) and attempt < retries - 1:
                await asyncio.sleep(1.0 * (attempt + 1))
        except Exception:
            if attempt < retries - 1:
                await asyncio.sleep(1.0 * (attempt + 1))
    return None


async def async_cf_post(url: str, data: str = "", headers: dict = None, timeout: int = 10, retries: int = 2):
    for attempt in range(retries):
        try:
            h = {"User-Agent": _UA}
            if headers:
                h.update(headers)
            r = await _get_async_session().post(url, data=data, headers=h, timeout=timeout)
            if r.status_code == 200:
                return r
        except Exception:
            if attempt < retries - 1:
                await asyncio.sleep(1.0 * (attempt + 1))
    return None


def close():
    _httpx_client.close()
    for s in _cffi_sessions:
        s.close()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            for s in _cffi_async_sessions:
                loop.create_task(s.close())
        else:
            for s in _cffi_async_sessions:
                loop.run_until_complete(s.close())
    except:
        pass
