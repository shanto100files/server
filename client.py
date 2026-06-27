"""
Shared HTTP client — OPTIMIZED for HuggingFace Free Tier.
Faster keepalive, tuned connection pool, exponential backoff.
Cloudflare bypass: rnet (TLS fingerprint) → cloudscraper (JS challenge) fallback chain.
"""
import httpx
import asyncio
import os
import random
import logging

try:
    from rnet import Client, AsyncClient, Emulation
    _rnet_client = Client(emulation=Emulation.Chrome120)
    _rnet_async_client = AsyncClient(emulation=Emulation.Chrome120)
    _HAS_RNET = True
except ImportError:
    _rnet_client = None
    _rnet_async_client = None
    _HAS_RNET = False
    logging.warning("rnet not installed — TLS fingerprint bypass unavailable")

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

# WARP proxy for CF-blocked domains (MLSBD etc.)
_WARP_PROXY = os.environ.get("WARP_PROXY_URL", "")
_PROXY_DOMAINS = {"mlsbd.co", "mlsbd.net", "mlsbd.com"}

def _needs_proxy(url: str) -> bool:
    if not _WARP_PROXY:
        return False
    try:
        host = urlparse(url).netloc.lower()
        return any(d in host for d in _PROXY_DOMAINS)
    except:
        return False

def _get_proxy_for_url(url: str) -> str | None:
    if _needs_proxy(url):
        return _WARP_PROXY
    return None

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

    if not _HAS_RNET:
        return None

    proxy = _get_proxy_for_url(url)
    try:
        r = _rnet_client.get(url, headers=h, timeout=timeout, proxy=proxy)
        if r.status == 200:
            return r.text
        if r.status != 403:
            return None
        html = r.text
    except Exception:
        return None

    if not _is_cf_challenge(html):
        return None

    cached = get_cached_cookie(url)
    if cached:
        cookie_str, cached_ua = cached
        retry_headers = {**h, "Cookie": cookie_str}
        try:
            r2 = _rnet_client.get(url, headers=retry_headers, timeout=timeout, proxy=proxy)
            if r2.status == 200:
                return r2.text
            from providers.cf_challenge_solver import invalidate_cookie
            invalidate_cookie(url)
        except Exception:
            pass

    cookie_str, meta = solve_challenge(url, html, _UA)
    if cookie_str:
        retry_headers = {**h, "Cookie": cookie_str}
        try:
            r3 = _rnet_client.get(url, headers=retry_headers, timeout=timeout, proxy=proxy)
            if r3.status == 200:
                return r3.text
        except Exception:
            pass

    return None


def cf_get(url: str, headers: dict = None, timeout: int = 10, retries: int = 3) -> str | None:
    h = {"User-Agent": _UA}
    if headers:
        h.update(headers)

    if _HAS_RNET:
        proxy = _get_proxy_for_url(url)
        for attempt in range(retries):
            try:
                r = _rnet_client.get(url, headers=h, timeout=timeout, proxy=proxy)
                if r.status == 200:
                    return r.text
                if r.status == 404:
                    return None
                if r.status in (403, 429) and attempt < retries - 1:
                    time.sleep(1.0 * (attempt + 1))
            except Exception:
                if attempt < retries - 1:
                    time.sleep(1.0 * (attempt + 1))

    solved = _cf_solve_and_retry(url, headers=h, timeout=timeout + 5)
    if solved:
        return solved

    return _cloudscraper_get(url, headers=h, timeout=timeout + 5)

def cf_post(url: str, data: str = "", headers: dict = None, timeout: int = 10, retries: int = 2):
    if _HAS_RNET:
        proxy = _get_proxy_for_url(url)
        for attempt in range(retries):
            try:
                h = {"User-Agent": _UA}
                if headers:
                    h.update(headers)
                r = _rnet_client.post(url, data=data, headers=h, timeout=timeout, proxy=proxy)
                if r.status == 200:
                    return r
                if r.status in (403, 429) and attempt < retries - 1:
                    time.sleep(1.0 * (attempt + 1))
            except Exception:
                if attempt < retries - 1:
                    time.sleep(1.0 * (attempt + 1))
    return None

async def async_cf_get(url: str, headers: dict = None, timeout: int = 10, retries: int = 3) -> str | None:
    h = {"User-Agent": _UA}
    if headers:
        h.update(headers)

    if _HAS_RNET:
        proxy = _get_proxy_for_url(url)
        for attempt in range(retries):
            try:
                r = await _rnet_async_client.get(url, headers=h, timeout=timeout, proxy=proxy)
                if r.status == 200:
                    return r.text
                if r.status == 404:
                    return None
                if r.status in (403, 429) and attempt < retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
            except Exception:
                if attempt < retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))

    solved = await asyncio.to_thread(_cf_solve_and_retry, url, h, timeout + 5)
    if solved:
        return solved

    return await asyncio.to_thread(_cloudscraper_get, url, h, timeout + 5)

async def async_cf_post(url: str, data: str = "", headers: dict = None, timeout: int = 10, retries: int = 2):
    if _HAS_RNET:
        proxy = _get_proxy_for_url(url)
        for attempt in range(retries):
            try:
                h = {"User-Agent": _UA}
                if headers:
                    h.update(headers)
                r = await _rnet_async_client.post(url, data=data, headers=h, timeout=timeout, proxy=proxy)
                if r.status == 200:
                    return r
                if r.status in (403, 429) and attempt < retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
            except Exception:
                if attempt < retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
    return None


def close():
    _httpx_client.close()
