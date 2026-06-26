import re
import json
import os
import sys
import time
from urllib.parse import urlparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from client import cf_get
from curl_cffi import requests as cffi_requests

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "domain_config.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"

KNOWN_PATTERNS = [
    ("gdflix", r"gdflix\.[a-z]+"),
    ("hubcloud", r"hubcloud\.[a-z]+"),
    ("cinecloud", r"cinecloud\.[a-z]+"),
    ("drivebot", r"drivebot\.[a-z]+"),
    ("fastdl", r"fastdl[a-z]*\.[a-z]+"),
]

PROVIDER_POSTS = [
    "https://southfreak.fyi/cocktail-2-2026",
    "https://southfreak.fyi/deadpool-wolverine-2024",
    "https://southfreak.fyi/mufasa-the-lion-king-2024",
    "https://mlsbd.co/cocktail-2-2026",
    "https://mlsbd.co/deadpool-wolverine-2024",
    "https://mlsbd.co/mufasa-the-lion-king-2024",
]


def extract_links(html: str) -> list[str]:
    return re.findall(r'href="(https?://[^"]+)"', html)


def extract_domains(html: str) -> dict:
    domains = {name: set() for name, _ in KNOWN_PATTERNS}
    links = extract_links(html)
    for link in links:
        host = urlparse(link).hostname or ""
        for name, pattern in KNOWN_PATTERNS:
            if re.search(pattern, host):
                domains[name].add(host)
    return domains


def fetch(url: str, timeout: int = 15) -> str | None:
    return cf_get(url, headers={"Referer": "https://southfreak.fyi", "User-Agent": UA}, timeout=timeout)


def follow_cffi(url: str, timeout: int = 10) -> tuple[str, str]:
    try:
        r = cffi_requests.get(url, impersonate="chrome", timeout=timeout, allow_redirects=True)
        return r.url, r.text
    except Exception:
        return url, ""


def discover_deep(urls: list[str] = None) -> dict:
    """Deep discovery - follow link protectors to find actual domains."""
    if urls is None:
        urls = PROVIDER_POSTS
    found = {name: set() for name, _ in KNOWN_PATTERNS}
    seen = set()

    def _check_text(text: str, source: str):
        for name, pattern in KNOWN_PATTERNS:
            for m in re.findall(pattern, text):
                found[name].add(m)

    for url in urls:
        print(f"  Fetching: {url}")
        html = fetch(url)
        if not html:
            continue
        _check_text(html, url)

        # Follow protector links (techzed.info, fxlinks.rest)
        for link in extract_links(html):
            host = urlparse(link).hostname or ""
            if any(x in host for x in ["techzed", "fxlinks", "fastdlserver"]):
                if link not in seen:
                    seen.add(link)
                    print(f"    Following: {link[:80]}")
                    final, body = follow_cffi(link, timeout=8)
                    _check_text(body or "", link)
                    if final != link:
                        _check_text(final, link)
                    # If it redirected to gdflix, follow that too
                    if "gdflix" in final and final not in seen:
                        seen.add(final)
                        body2 = fetch(final, timeout=12)
                        if body2:
                            _check_text(body2, final)

    return {k: sorted(v) for k, v in found.items()}


def update_config(discovered: dict):
    with open(_CONFIG_PATH, "r") as f:
        config = json.load(f)
    updated = False
    for provider, domains in discovered.items():
        if provider in config and isinstance(config[provider], dict):
            existing = set(config[provider].get("domains", []))
            new_domains = set(domains) - existing
            if new_domains:
                print(f"  New {provider} domains: {new_domains}")
                config[provider]["domains"] = sorted(existing | new_domains)
                updated = True
    if updated:
        config["_updated"] = time.strftime("%Y-%m-%d %H:%M")
        with open(_CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        print("  Updated domain_config.json")
    else:
        print("  No new domains found")
    return config


if __name__ == "__main__":
    print("=== Deep Domain Discovery ===")
    discovered = discover_deep(PROVIDER_POSTS)
    print(f"\nDiscovered:")
    for name, domains in discovered.items():
        print(f"  {name}: {domains}")
    print(f"\nUpdating config...")
    update_config(discovered)
    print("Done!")
