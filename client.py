"""
Shared HTTP client — OPTIMIZED for HuggingFace Free Tier.
Faster keepalive, tuned connection pool, exponential backoff.
Cloudflare bypass: curl_cffi (TLS fingerprint) → cloudscraper (JS challenge) fallback chain.
"""
import httpx
import asyncio
import os
import random
import logging
from curl_cffi import requests as cffi_requests

try:
    import cloudscraper as _cloudscraper
    _scraper = _cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
        interpreter="js2py",
    )
    _HAS_CLOUDSCRAPER = True
except ImportError:
    _scraper = None
    _HAS_CLOUDSCRAPER = False
    logging.warning("cloudscraper not installed — JS challenge bypass unavailable")

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

_httpx_client = httpx.Client(
    timeout=httpx.Timeout(10.0),
    limits=httpx.Limits(
        max_connections=40,
        max_keepalive_connections=20,
        keepalive_expiry=45,
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
    pass

# Run proxy fetch in background once
# threading.Thread(target=_fetch_free_proxies, daemon=True).start()

_IMPERSONATES = ["chrome110", "chrome116", "chrome120", "edge101", "safari15_3"]

# WARP proxy for CF-blocked domains (MLSBD etc.)
_WARP_PROXY = os.environ.get("WARP_PROXY_URL", "")
_PROXY_DOMAINS = {"mlsbd.co", "mlsbd.net", "mlsbd.com"}

def _needs_proxy(url: str) -> bool:
    """Check if a URL's domain needs WARP proxy."""
    if not _WARP_PROXY:
        return False
    try:
        host = urlparse(url).netloc.lower()
        return any(d in host for d in _PROXY_DOMAINS)
    except:
        return False

def _get_proxy_for_url(url: str) -> dict | None:
    """Return proxy dict for domains that need WARP."""
    if _needs_proxy(url):
        return {"http": _WARP_PROXY, "https": _WARP_PROXY}
    return None

_domain_sync_sessions = {}
_domain_async_sessions = {}
_session_lock = threading.Lock()

def _get_proxy():
    return None

def _get_sync_session(url: str):
    domain = urlparse(url).netloc
    with _session_lock:
        if domain not in _domain_sync_sessions:
            imp = random.choice(_IMPERSONATES)
            proxy = _get_proxy_for_url(url)
            _domain_sync_sessions[domain] = cffi_requests.Session(impersonate=imp, proxies=proxy)
        return _domain_sync_sessions[domain]

def _get_async_session(url: str):
    domain = urlparse(url).netloc
    with _session_lock:
        if domain not in _domain_async_sessions:
            imp = random.choice(_IMPERSONATES)
            proxy = _get_proxy_for_url(url)
            _domain_async_sessions[domain] = cffi_requests.AsyncSession(impersonate=imp, proxies=proxy)
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

def _cloudscraper_get(url: str, headers: dict = None, timeout: int = 15) -> str | None:
    """Fallback: solve JS challenge via cloudscraper (no browser)."""
    if not _HAS_CLOUDSCRAPER or _scraper is None:
        return None
    try:
        h = {"User-Agent": _UA}
        if headers:
            h.update(headers)
        r = _scraper.get(url, headers=h, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        logging.debug("cloudscraper failed for %s: %s", url, e)
    return None


def _cf_solve_and_retry(url: str, headers: dict = None, timeout: int = 15) -> str | None:
    """
    Try to solve CF challenge via cf_challenge_solver + retry with cookie.
    Chain: detect challenge → get/solve cookie → retry with cookie.
    """
    try:
        from providers.cf_challenge_solver import (
            _is_cf_challenge, get_cached_cookie, solve_challenge, should_skip_cf_solve,
        )
    except ImportError:
        try:
            from cf_challenge_solver import (
                _is_cf_challenge, get_cached_cookie, solve_challenge, should_skip_cf_solve,
            )
        except ImportError:
            return None

    if should_skip_cf_solve(url):
        return None

    h = {"User-Agent": _UA}
    if headers:
        h.update(headers)

    # Try curl_cffi first to get the challenge page
    try:
        r = _get_sync_session(url).get(url, headers=h, timeout=timeout)
        if r.status_code == 200:
            return r.text
        if r.status_code != 403:
            return None
        html = r.text
    except Exception:
        return None

    if not _is_cf_challenge(html):
        return None

    # Check cache first
    cached = get_cached_cookie(url)
    if cached:
        cookie_str, cached_ua = cached
        retry_headers = {**h, "Cookie": cookie_str}
        try:
            session = cffi_requests.Session(impersonate=random.choice(_IMPERSONATES))
            r2 = session.get(url, headers=retry_headers, timeout=timeout)
            if r2.status_code == 200:
                return r2.text
            # Cached cookie expired — invalidate
            from providers.cf_challenge_solver import invalidate_cookie
            invalidate_cookie(url)
        except Exception:
            pass

    # Try to solve the challenge
    cookie_str, meta = solve_challenge(url, html, _UA)
    if cookie_str:
        retry_headers = {**h, "Cookie": cookie_str}
        try:
            session = cffi_requests.Session(impersonate=random.choice(_IMPERSONATES))
            r3 = session.get(url, headers=retry_headers, timeout=timeout)
            if r3.status_code == 200:
                return r3.text
        except Exception:
            pass

    return None


def cf_get(url: str, headers: dict = None, timeout: int = 10, retries: int = 3) -> str | None:
    """Try curl_cffi → cf_solver → cloudscraper fallback chain."""
    h = {"User-Agent": _UA}
    if headers:
        h.update(headers)

    for attempt in range(retries):
        try:
            r = _get_sync_session(url).get(url, headers=h, timeout=timeout)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None

            if r.status_code in (403, 429):
                with _session_lock:
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

    # curl_cffi exhausted → try CF challenge solver (detect + cache cookie + retry)
    solved = _cf_solve_and_retry(url, headers=h, timeout=timeout + 5)
    if solved:
        return solved

    # CF solver couldn't handle → try cloudscraper JS challenge bypass
    return _cloudscraper_get(url, headers=h, timeout=timeout + 5)

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
    """Async: try curl_cffi → cf_solver → cloudscraper (via thread pool) fallback chain."""
    h = {"User-Agent": _UA}
    if headers:
        h.update(headers)

    for attempt in range(retries):
        try:
            r = await _get_async_session(url).get(url, headers=h, timeout=timeout)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
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

    # curl_cffi exhausted → try CF solver (sync via thread pool)
    solved = await asyncio.to_thread(_cf_solve_and_retry, url, h, timeout + 5)
    if solved:
        return solved

    # CF solver couldn't handle → try cloudscraper (sync via thread pool)
    return await asyncio.to_thread(_cloudscraper_get, url, h, timeout + 5)

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
