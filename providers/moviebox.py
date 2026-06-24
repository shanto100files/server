import hashlib
import hmac
import json
import time
import random
import string
import base64
from urllib.parse import urlencode
from client import http_get

API_BASE = "https://api3.aoneroom.com"

SECRET_KEY_DEFAULT = base64.b64decode(
    base64.b64decode("NzZpUmwwN3MweFNOOWpxbUVXQXQ3OUVCSlp1bElRSXNWNjRGWnIyTw==").decode("ascii")
)

def _md5hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def _generate_device_id() -> str:
    return "".join(random.choices("0123456789abcdef", k=32))

def _generate_client_token() -> str:
    ts = str(int(time.time() * 1000))
    reversed_ts = ts[::-1]
    return f"{ts},{_md5hex(reversed_ts)}"

def _build_canonical_string(method, accept, content_type, url, body, timestamp):
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    path = parsed.path or "/"
    qs = parse_qs(parsed.query, keep_blank_values=True)
    sorted_keys = sorted(qs.keys())
    sorted_params = []
    for k in sorted_keys:
        for v in qs[k]:
            sorted_params.append(f"{k}={v}")
    canonical_url = f"{path}?{'&'.join(sorted_params)}" if sorted_params else path

    body_hash = ""
    body_length = ""
    if body is not None:
        body_bytes = body.encode("utf-8")
        body_length = str(len(body_bytes))
        trimmed = body_bytes[:102400]
        body_hash = hashlib.md5(trimmed).hexdigest()

    return f"{method.upper()}\n{accept or ''}\n{content_type or ''}\n{body_length}\n{timestamp}\n{body_hash}\n{canonical_url}"

def _generate_x_tr_signature(method, accept, content_type, url, body=None):
    timestamp = int(time.time() * 1000)
    canonical = _build_canonical_string(method, accept, content_type, url, body, timestamp)
    sig = hmac.new(SECRET_KEY_DEFAULT, canonical.encode("utf-8"), hashlib.md5).digest()
    signature = base64.b64encode(sig).decode()
    return f"{timestamp}|2|{signature}"

def _mbox_headers(device_id, extra=None):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "User-Agent": "com.community.mbox.in/50020042 (Linux; U; Android 16; en_IN; sdk_gphone64_x86_64; Build/BP22.250325.006; Cronet/133.0.6876.3)",
        "x-client-token": _generate_client_token(),
        "x-client-info": json.dumps({
            "package_name": "com.community.mbox.in",
            "version_name": "3.0.03.0529.03",
            "version_code": 50020042,
            "os": "android",
            "os_version": "16",
            "device_id": device_id,
            "install_store": "ps",
            "gaid": "d7578036d13336cc",
            "brand": "google",
            "model": "SM-S918B",
            "system_language": "en",
            "net": "NETWORK_WIFI",
            "region": "IN",
            "timezone": "Asia/Calcutta",
            "sp_code": ""
        }),
        "x-client-status": "0",
    }
    if extra:
        headers.update(extra)
    return headers

def _oneroom_headers(device_id, extra=None):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "User-Agent": "com.community.oneroom/50020088 (Linux; U; Android 13; en_US; SM-S918B; Build/TQ3A.230901.001; Cronet/145.0.7582.0)",
        "x-client-token": _generate_client_token(),
        "x-client-info": json.dumps({
            "package_name": "com.community.oneroom",
            "version_name": "3.0.13.0325.03",
            "version_code": 50020088,
            "os": "android",
            "os_version": "13",
            "install_ch": "ps",
            "device_id": device_id,
            "install_store": "ps",
            "gaid": "1b2212c1-dadf-43c3-a0c8-bd6ce48ae22d",
            "brand": "google",
            "model": "SM-S918B",
            "system_language": "en",
            "net": "NETWORK_WIFI",
            "region": "US",
            "timezone": "Asia/Calcutta",
            "sp_code": "",
            "X-Play-Mode": "1",
            "X-Idle-Data": "1",
            "X-Family-Mode": "0",
            "X-Content-Mode": "0"
        }),
        "x-client-status": "0",
    }
    if extra:
        headers.update(extra)
    return headers

def _api_get(url, headers):
    r = http_get(url, headers=headers, timeout=20)
    if r and r.status_code == 200:
        return {"status": r.status_code, "body": r.text, "headers": dict(r.headers)}
    return None

def _api_post(url, headers, body):
    import httpx
    try:
        r = httpx.post(url, headers=headers, content=body.encode("utf-8"), timeout=20)
        return {"status": r.status_code, "body": r.text, "headers": dict(r.headers)}
    except Exception:
        return None


_device_id = _generate_device_id()


def moviebox_search(query: str) -> list[dict]:
    url = f"{API_BASE}/wefeed-mobile-bff/subject-api/search/v2"
    body = json.dumps({"page": 1, "perPage": 20, "keyword": query})
    headers = _mbox_headers(_device_id, {
        "x-tr-signature": _generate_x_tr_signature(
            "POST", "application/json", "application/json; charset=utf-8", url, body
        ),
        "x-play-mode": "2",
        "Content-Type": "application/json; charset=utf-8",
    })

    res = _api_post(url, headers, body)
    if not res:
        return []

    try:
        data = json.loads(res["body"])
    except Exception:
        return []

    results = data.get("data", {}).get("results", [])
    subjects = []
    for result in results:
        for subject in result.get("subjects", []):
            subjects.append(subject)
    return subjects


def moviebox_get_subject_info(subject_id: str) -> dict:
    url = f"{API_BASE}/wefeed-mobile-bff/subject-api/get?subjectId={subject_id}"
    headers = _oneroom_headers(_device_id, {
        "x-tr-signature": _generate_x_tr_signature("GET", "application/json", "application/json", url),
    })

    res = _api_get(url, headers)
    if not res:
        return {"data": None, "token": None}

    token = None
    x_user_raw = res["headers"].get("x-user")
    if x_user_raw:
        try:
            x_user = json.loads(x_user_raw)
            token = x_user.get("token")
        except Exception:
            pass

    try:
        data = json.loads(res["body"])
        return {"data": data.get("data"), "token": token}
    except Exception:
        return {"data": None, "token": None}


def moviebox_get_play_info(subject_id: str, season: int, episode: int, token: str = None) -> list:
    url = f"{API_BASE}/wefeed-mobile-bff/subject-api/play-info?subjectId={subject_id}&se={season}&ep={episode}"
    headers = _oneroom_headers(_device_id, {
        "x-tr-signature": _generate_x_tr_signature("GET", "application/json", "application/json", url),
    })
    if token:
        headers["Authorization"] = f"Bearer {token}"

    res = _api_get(url, headers)
    if not res:
        return []

    try:
        data = json.loads(res["body"])
        return data.get("data", {}).get("streams", [])
    except Exception:
        return []


def moviebox(title: str, tmdb_id: str = "", media_type: str = "movie", season: int = 0, episode: int = 0) -> list[dict]:
    sources = []

    subjects = moviebox_search(title)
    if not subjects:
        return sources

    subject = subjects[0]
    subject_id = subject.get("subjectId")
    if not subject_id:
        return sources

    info = moviebox_get_subject_info(subject_id)
    subject_data = info.get("data")
    token = info.get("token")
    if not subject_data:
        return sources

    subject_ids = []
    dubs = subject_data.get("dubs", [])
    original_lang = "Original"
    for dub in dubs:
        if dub.get("subjectId") == subject_id:
            original_lang = dub.get("lanName", "Original")
        else:
            subject_ids.append({"id": dub.get("subjectId"), "language": dub.get("lanName", "Unknown")})
    subject_ids.insert(0, {"id": subject_id, "language": original_lang})

    for sub in subject_ids:
        try:
            streams = moviebox_get_play_info(sub["id"], season, episode, token)
            for stream in streams:
                stream_url = stream.get("url", "")
                if not stream_url:
                    continue

                fmt = (stream.get("format", "")).upper()
                resolutions = stream.get("resolutions", "")

                source_format = "mp4"
                if fmt == "HLS" or stream_url.endswith(".m3u8"):
                    source_format = "m3u8"
                elif fmt == "DASH" or stream_url.endswith(".mpd"):
                    source_format = "mpd"

                quality = "1080"
                for q in ["2160", "1080", "720", "480", "360"]:
                    if q in str(resolutions):
                        quality = q
                        break

                referer = API_BASE
                sign_cookie = stream.get("signCookie", "")

                sources.append({
                    "url": stream_url,
                    "quality": f"{quality}p",
                    "provider": "MovieBox",
                    "format": source_format,
                    "language": sub["language"],
                    "cookie": sign_cookie,
                    "referer": referer,
                })
        except Exception:
            continue

    return sources
