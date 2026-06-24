import time
import json
import os
from urllib.parse import urlparse
from curl_cffi import requests as cffi_requests
from client import cf_get

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "domain_config.json")
_STATE_PATH = os.path.join(os.path.dirname(__file__), "domain_state.json")

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"


def _load_config():
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_state():
    try:
        with open(_STATE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: dict):
    try:
        with open(_STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def check_domain(domain: str, timeout: int = 8) -> dict:
    url = f"https://{domain}"
    start = time.time()
    try:
        r = cffi_requests.get(url, impersonate="chrome", timeout=timeout, allow_redirects=True)
        elapsed = time.time() - start
        return {
            "domain": domain,
            "status": r.status_code,
            "alive": r.status_code < 400,
            "response_time": round(elapsed, 2),
            "final_url": r.url,
            "checked_at": time.time(),
        }
    except Exception as e:
        return {
            "domain": domain,
            "status": 0,
            "alive": False,
            "response_time": round(time.time() - start, 2),
            "error": str(e)[:100],
            "checked_at": time.time(),
        }


def check_all_domains() -> dict:
    config = _load_config()
    results = {}

    for provider, data in config.items():
        if provider.startswith("_"):
            continue
        if isinstance(data, dict) and "domains" in data:
            results[provider] = []
            for domain in data["domains"]:
                result = check_domain(domain)
                results[provider].append(result)

    _save_state(results)
    return results


def get_working_domain(provider: str) -> str | None:
    state = _load_state()
    if provider in state:
        for domain_result in state[provider]:
            if domain_result.get("alive"):
                return domain_result["domain"]

    config = _load_config()
    provider_config = config.get(provider, {})
    domains = provider_config.get("domains", [])

    for domain in domains:
        result = check_domain(domain)
        if result["alive"]:
            return domain

    return None


def get_all_status() -> dict:
    state = _load_state()
    if not state:
        state = check_all_domains()

    summary = {}
    for provider, domain_results in state.items():
        if not isinstance(domain_results, list):
            continue
        working = [d for d in domain_results if d.get("alive")]
        summary[provider] = {
            "total": len(domain_results),
            "working": len(working),
            "domains": {
                d["domain"]: {
                    "alive": d.get("alive", False),
                    "status": d.get("status", 0),
                    "response_time": d.get("response_time", 0),
                }
                for d in domain_results
            }
        }

    return summary
