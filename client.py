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

import threading
from urllib.parse import urlparse
import time

_PROXIES = []
_proxy_file = os.path.join(os.path.dirname(__file__), "proxies.txt")

def _load_proxies():
    global _PROXIES
    if os.path.exists(_proxy_file):
        with open(_proxy_file, "r") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            _PROXIES = [{"http": p, "https": p} for p in lines]

_load_proxies()

def _fetch_free_proxies():
    try:
        r = httpx.get("https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt", timeout=10)
        if r.status_code == 200:
            lines = r.text.split("\n")[:100] # Take top 100
            with open(_proxy_file, "w") as f:
                f.write("\n".join(lines))
            _load_proxies()
    except:
        pass

# Run proxy fetch in background once
threading.Thread(target=_fetch_free_proxies, daemon=True).start()

_IMPERSONATES = ["chrome110", "chrome116", "chrome120", "edge101", "safari15_3"]

_domain_sync_sessions = {}
_domain_async_sessions = {}
_session_lock = threading.Lock()

def _get_proxy():
    return random.choice(_PROXIES) if _PROXIES else None

def _get_sync_session(url: str):
    domain = urlparse(url).netloc
    with _session_lock:
        if domain not in _domain_sync_sessions:
            imp = random.choice(_IMPERSONATES)
            _domain_sync_sessions[domain] = cffi_requests.Session(impersonate=imp, proxies=_get_proxy())
        return _domain_sync_sessions[domain]

def _get_async_session(url: str):
    domain = urlparse(url).netloc
    with _session_lock:
        if domain not in _domain_async_sessions:
            imp = random.choice(_IMPERSONATES)
            _domain_async_sessions[domain] = cffi_requests.AsyncSession(impersonate=imp, proxies=_get_proxy())
        return _domain_async_sessions[domain]

def http_get(url: str, headers: dict = None, timeout: int = 10, retries: int = 2) -> httpx.Response | None:
    for attempt in range(retries):
        try:
            r = _httpx_client.get(url, headers=headers or {}, timeout=timeout)
            if r.status_code == 200:
                return r
        except Exception:
            if attempt < retries - 1:
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
            r = _get_sync_session(url).get(url, headers=h, timeout=timeout)
            if r.status_code in (200, 404):
                if r.status_code == 200:
                    return r.text
                return None
            
            if r.status_code in (403, 429):
                with _session_lock: # Reset session on ban
                    domain = urlparse(url).netloc
                    _domain_sync_sessions.pop(domain, None)
                if attempt < retries - 1:
                    time.sleep(1.0 * (attempt + 1))
        except Exception:
            with _session_lock:
                domain = urlparse(url).netloc
                _domain_sync_sessions.pop(domain, None)
            if attempt < retries - 1:
                time.sleep(1.0 * (attempt + 1))
    return None

def cf_post(url: str, data: str = "", headers: dict = None, timeout: int = 10, retries: int = 2) -> httpx.Response | None:
    for attempt in range(retries):
        try:
            h = {"User-Agent": _UA}
            if headers:
                h.update(headers)
            r = _get_sync_session(url).post(url, data=data, headers=h, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429):
                with _session_lock:
                    domain = urlparse(url).netloc
                    _domain_sync_sessions.pop(domain, None)
        except Exception:
            with _session_lock:
                domain = urlparse(url).netloc
                _domain_sync_sessions.pop(domain, None)
            if attempt < retries - 1:
                time.sleep(1.0 * (attempt + 1))
    return None

async def async_cf_get(url: str, headers: dict = None, timeout: int = 10, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            h = {"User-Agent": _UA}
            if headers:
                h.update(headers)
            r = await _get_async_session(url).get(url, headers=h, timeout=timeout)
            if r.status_code in (200, 404):
                if r.status_code == 200:
                    return r.text
                return None

            if r.status_code in (403, 429):
                with _session_lock:
                    domain = urlparse(url).netloc
                    _domain_async_sessions.pop(domain, None)
                if attempt < retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
        except Exception:
            with _session_lock:
                domain = urlparse(url).netloc
                _domain_async_sessions.pop(domain, None)
            if attempt < retries - 1:
                await asyncio.sleep(1.0 * (attempt + 1))
    return None

async def async_cf_post(url: str, data: str = "", headers: dict = None, timeout: int = 10, retries: int = 2):
    for attempt in range(retries):
        try:
            h = {"User-Agent": _UA}
            if headers:
                h.update(headers)
            r = await _get_async_session(url).post(url, data=data, headers=h, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429):
                with _session_lock:
                    domain = urlparse(url).netloc
                    _domain_async_sessions.pop(domain, None)
        except Exception:
            with _session_lock:
                domain = urlparse(url).netloc
                _domain_async_sessions.pop(domain, None)
            if attempt < retries - 1:
                await asyncio.sleep(1.0 * (attempt + 1))
    return None


def close():
    _httpx_client.close()
    with _session_lock:
        for s in _domain_sync_sessions.values():
            try: s.close()
            except: pass
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                for s in _domain_async_sessions.values():
                    loop.create_task(s.close())
            else:
                for s in _domain_async_sessions.values():
                    loop.run_until_complete(s.close())
        except:
            pass
