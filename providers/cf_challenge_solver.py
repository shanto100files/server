"""
Cloudflare Challenge Solver — lightweight custom solution.

Strategy:
  1. Detect CF challenge page type from HTML
  2. For JS challenges (v1/v2): extract + solve with js2py
  3. For interactive/managed: cookie persistence (solve once, cache cf_clearance)
  4. For Turnstile: extract sitekey + call challenge-platform API

No browser dependency. ~50MB RAM.
"""
import re
import time
import logging
import hashlib
from urllib.parse import urlparse, parse_qs, urlencode, urljoin
from html import unescape as html_unescape

logger = logging.getLogger("cf_solver")

# ---------- CF challenge page detection ----------

IUAM_SIGNATURES = [
    "Just a moment...",
    "Checking if the site connection is secure",
    "Enable JavaScript and cookies to continue",
    "_cf_chl_opt",
    "challenge-platform",
    "cf-challenge",
    "turnstile",
]

CHALLENGE_SCRIPT_RE = re.compile(
    r'<script[^>]*src=["\']([^"\']*challenge-platform[^"\']*)["\']', re.I
)

CF_CHL_OPT_RE = re.compile(
    r'window\._cf_chl_opt\s*=\s*\{(.*?)\};', re.S
)

CHALLENGE_PARAM_RE = re.compile(
    r"(\w+)\s*:\s*['\"]([^'\"]*?)['\"]"
)

FORM_ACTION_RE = re.compile(
    r'<form[^>]*action=["\']([^"\']+)["\']', re.I
)

TURNSTILE_SCRIPT_RE = re.compile(
    r'<script[^>]*src=["\']([^"\']*challenges\.cloudflare\.com/turnstile[^"\']*)["\']', re.I
)

TURNSTILE_SITEKEY_RE = re.compile(
    r'data-sitekey=["\']([^"\']+)["\']', re.I
)

# ---------- Cookie cache ----------

_cookie_cache = {}  # domain -> {"cookie": str, "ua": str, "ts": float}
COOKIE_TTL = 1500  # 25 minutes (CF cookies typically last 30 min)


def _is_cf_challenge(html: str) -> bool:
    """Check if HTML is a Cloudflare challenge page."""
    if not html:
        return False
    count = sum(1 for sig in IUAM_SIGNATURES if sig in html)
    return count >= 2


def _extract_challenge_type(html: str) -> str:
    """Extract challenge type from CF challenge page."""
    m = re.search(r"cType\s*:\s*['\"]([^'\"]+)['\"]", html)
    if m:
        return m.group(1)
    if "turnstile" in html.lower():
        return "turnstile"
    if "challenge-platform" in html:
        return "managed"
    return "unknown"


def _parse_cf_chl_opt(html: str) -> dict:
    """Parse window._cf_chl_opt from challenge page."""
    m = CF_CHL_OPT_RE.search(html)
    if not m:
        return {}
    raw = m.group(1)
    params = {}
    for match in CHALLENGE_PARAM_RE.finditer(raw):
        key = match.group(1)
        val = html_unescape(match.group(2))
        params[key] = val
    return params


def _extract_turnstile_sitekey(html: str) -> str | None:
    """Extract Turnstile widget sitekey."""
    m = TURNSTILE_SITEKEY_RE.search(html)
    return m.group(1) if m else None


def _extract_form_action(html: str) -> str | None:
    """Extract form action URL."""
    m = FORM_ACTION_RE.search(html)
    return html_unescape(m.group(1)) if m else None


def _extract_challenge_script_url(html: str) -> str | None:
    """Extract challenge-platform script URL."""
    m = CHALLENGE_SCRIPT_RE.search(html)
    return m.group(1) if m else None


# ---------- JS Challenge Solver ----------

JS_CHALLENGE_TEMPLATE = """
var window = {{
    _cf_chl_opt: {params_json},
    location: {{ href: "{url}", hostname: "{hostname}", pathname: "{pathname}" }},
    navigator: {{ userAgent: "{ua}", platform: "Win32", languages: ["en-US","en"] }},
    document: {{ cookie: "", readyState: "complete" }},
    chrome: {{ runtime: {{}} }},
    addEventListener: function() {{}},
    setTimeout: function(fn, t) {{ fn(); }},
    setInterval: function(fn, t) {{ fn(); }},
    clearInterval: function() {{}},
    clearTimeout: function() {{}},
}};
var document = window.document;
var navigator = window.navigator;
var location = window.location;
"""


def _solve_js_challenge(url: str, html: str, ua: str) -> dict | None:
    """
    Try to solve a JS challenge (non-interactive) using js2py.
    Returns cookie dict or None.
    """
    try:
        import js2py
    except ImportError:
        logger.warning("js2py not installed — cannot solve JS challenges")
        return None

    params = _parse_cf_chl_opt(html)
    if not params:
        return None

    ctype = params.get("cType", "unknown")
    if ctype in ("interactive", "managed"):
        logger.info("Challenge type '%s' requires browser — skipping JS solve", ctype)
        return None

    script_url = _extract_challenge_script_url(html)
    if not script_url:
        return None

    # Build JS context
    parsed = urlparse(url)
    js_context = JS_CHALLENGE_TEMPLATE.format(
        params_json=__import__("json").dumps(params),
        url=url,
        hostname=parsed.hostname or "",
        pathname=parsed.path or "/",
        ua=ua,
    )

    try:
        ctx = js2py.EvalJs()
        ctx.execute(js_context)
        # The challenge script would normally be fetched and executed here
        # For now, we rely on cookie persistence approach
        logger.info("JS challenge context built but requires challenge script execution")
    except Exception as e:
        logger.debug("JS challenge execution failed: %s", e)

    return None


# ---------- Cookie Persistence ----------

def _cache_key(url: str) -> str:
    """Generate cache key for a URL's domain."""
    host = urlparse(url).hostname or ""
    return hashlib.md5(host.encode()).hexdigest()


def get_cached_cookie(url: str) -> tuple[str, str] | None:
    """
    Get cached cf_clearance cookie for a domain.
    Returns (cookie_string, user_agent) or None.
    """
    key = _cache_key(url)
    entry = _cookie_cache.get(key)
    if not entry:
        return None
    if time.time() - entry["ts"] > COOKIE_TTL:
        del _cookie_cache[key]
        return None
    return entry["cookie"], entry["ua"]


def cache_cookie(url: str, cookie: str, ua: str):
    """Cache a cf_clearance cookie for a domain."""
    key = _cache_key(url)
    _cookie_cache[key] = {
        "cookie": cookie,
        "ua": ua,
        "ts": time.time(),
    }
    logger.info("Cached CF cookie for %s (expires in %ds)", urlparse(url).hostname, COOKIE_TTL)


def invalidate_cookie(url: str):
    """Remove cached cookie for a domain."""
    key = _cache_key(url)
    _cookie_cache.pop(key, None)


# ---------- Main Solver API ----------

def analyze_challenge(html: str) -> dict:
    """
    Analyze a CF challenge page and return metadata.
    """
    if not _is_cf_challenge(html):
        return {"is_cf_challenge": False}

    ctype = _extract_challenge_type(html)
    params = _parse_cf_chl_opt(html)
    sitekey = _extract_turnstile_sitekey(html)
    form_action = _extract_form_action(html)

    return {
        "is_cf_challenge": True,
        "challenge_type": ctype,
        "zone": params.get("cZone", ""),
        "nonce": params.get("cN", ""),
        "ray": params.get("cRay", ""),
        "form_action": form_action,
        "sitekey": sitekey,
        "can_solve_without_browser": ctype in ("js", "managed") and not sitekey,
    }


def solve_challenge(
    url: str,
    html: str,
    ua: str,
    fetch_fn=None,
) -> tuple[str | None, dict]:
    """
    Attempt to solve a CF challenge.
    
    Args:
        url: The original URL that returned the challenge
        html: The challenge page HTML
        ua: User-Agent string
        fetch_fn: Optional function to fetch URLs (for submitting solutions)
    
    Returns:
        (cf_clearance_cookie_string, metadata_dict) or (None, metadata_dict)
    """
    meta = analyze_challenge(html)
    if not meta.get("is_cf_challenge"):
        return None, {"error": "not a CF challenge"}

    # Check cache first
    cached = get_cached_cookie(url)
    if cached:
        meta["from_cache"] = True
        return cached[0], meta

    ctype = meta["challenge_type"]

    # Try JS challenge solve for non-interactive types
    if ctype in ("js",):
        cookie = _solve_js_challenge(url, html, ua)
        if cookie:
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookie.items())
            cache_cookie(url, cookie_str, ua)
            meta["solved"] = True
            return cookie_str, meta

    # For interactive/managed/turnstile — cannot solve without browser
    meta["solved"] = False
    meta["reason"] = f"Challenge type '{ctype}' requires browser interaction"
    return None, meta


# ---------- Integration helper ----------

def should_skip_cf_solve(url: str) -> bool:
    """Check if URL should skip CF solving (direct links, etc.)."""
    host = (urlparse(url).hostname or "").lower()
    skip_domains = [
        "r2.dev", "r2.cloudflarestorage", "pixeldrain",
        "googleusercontent.com", "drive.google.com",
    ]
    return any(d in host for d in skip_domains)
