import json
import re
import base64
from client import http_get, http_post, cf_get

CASTLE_BASE = "https://api.hlowb.com"
CHANNEL = "IndiaA"
CLIENT_TYPE = "1"
LANG = "en-US"

_security_key_cache = None

def _get_security_key() -> str:
    global _security_key_cache
    if _security_key_cache:
        return _security_key_cache
    try:
        r = http_get(
            f"{CASTLE_BASE}/v0.1/system/getSecurityKey/1",
            headers={"channel": CHANNEL, "clientType": CLIENT_TYPE, "lang": LANG},
            timeout=10,
        )
        if r:
            data = r.json()
            _security_key_cache = data.get("data", "")
            return _security_key_cache
    except:
        pass
    return ""

def _decrypt_aes(ciphertext: str) -> dict | None:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend

        key_b64 = _get_security_key()
        if not key_b64:
            return None

        raw_key = base64.b64decode(key_b64)
        pad_key = (raw_key + b"T!BgJB")[:16]

        ct = base64.b64decode(ciphertext)
        iv = pad_key

        cipher = Cipher(algorithms.AES(pad_key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        pt = decryptor.update(ct) + decryptor.finalize()

        pk = pt[-1]
        if isinstance(pk, int) and 1 <= pk <= 16:
            pt = pt[:-pk]

        text = pt.decode("utf-8", errors="ignore")
        text = re.sub(r'"(\w*Id|id)": (-?\d+)', r'"\1": "\2"', text)
        return json.loads(text)
    except:
        return None

def _api_get(path: str, params: dict = None) -> dict | None:
    try:
        p = {"channel": CHANNEL, "clientType": CLIENT_TYPE, "lang": LANG, "packageName": "com.external.castle"}
        if params:
            p.update(params)
        url = f"{CASTLE_BASE}{path}"
        r = http_get(url, params=p, timeout=10)
        if r:
            data = r.json()
            resp_data = data.get("data", "")
            if isinstance(resp_data, str) and resp_data:
                decrypted = _decrypt_aes(resp_data)
                if decrypted:
                    return decrypted
            return data
    except:
        return None

def _api_post(path: str, body: dict) -> dict | None:
    try:
        params = {"clientType": CLIENT_TYPE, "packageName": "com.external.castle", "channel": CHANNEL, "lang": LANG}
        url = f"{CASTLE_BASE}{path}"
        r = http_post(url, content=json.dumps(body), headers={"Content-Type": "application/json"}, timeout=10)
        if r:
            data = r.json()
            resp_data = data.get("data", "")
            if isinstance(resp_data, str) and resp_data:
                decrypted = _decrypt_aes(resp_data)
                if decrypted:
                    return decrypted
            return data
    except:
        return None

def castletv_search(query: str) -> list[dict]:
    sources = []
    data = _api_get("/film-api/v1.1.0/movie/searchByKeyword", {"keyword": query, "mode": "1", "page": "1", "size": "30"})
    if not data:
        return sources

    items = data.get("list", data.get("data", {}).get("list", []))
    if not items:
        return sources

    for item in items[:3]:
        movie_id = item.get("movieId") or item.get("id")
        if not movie_id:
            continue

        movie_data = _api_get("/film-api/v1.9.9/movie", {"movieId": str(movie_id)})
        if not movie_data:
            continue

        streams = _extract_streams(movie_data, str(movie_id))
        sources.extend(streams)

    return sources

def _extract_streams(movie_data: dict, movie_id: str) -> list[dict]:
    streams = []
    episodes = movie_data.get("episodes", movie_data.get("episodeList", []))

    if episodes:
        for ep in episodes:
            ep_id = ep.get("episodeId") or ep.get("id")
            ep_name = ep.get("title", f"Episode {ep_id}")
            if not ep_id:
                continue

            video_resp = _api_post(
                f"/film-api/v2.0.1/movie/getVideo2",
                {
                    "mode": "1",
                    "appMarket": "GuanWang",
                    "clientType": CLIENT_TYPE,
                    "woolUser": "false",
                    "apkSignKey": "ED0955EB04E67A1D9F3305B95454FED485261475",
                    "androidVersion": "13",
                    "movieId": movie_id,
                    "episodeId": str(ep_id),
                    "isNewUser": "true",
                    "resolution": "3",
                    "packageName": "com.external.castle",
                },
            )
            if video_resp:
                video_url = video_resp.get("videoUrl", "")
                if video_url:
                    streams.append({
                        "url": video_url,
                        "quality": "1080p",
                        "provider": "CastleTV",
                        "format": "hls",
                    })
    else:
        video_resp = _api_post(
            f"/film-api/v2.0.1/movie/getVideo2",
            {
                "mode": "1",
                "appMarket": "GuanWang",
                "clientType": CLIENT_TYPE,
                "woolUser": "false",
                "apkSignKey": "ED0955EB04E67A1D9F3305B95454FED485261475",
                "androidVersion": "13",
                "movieId": movie_id,
                "episodeId": "0",
                "isNewUser": "true",
                "resolution": "3",
                "packageName": "com.external.castle",
            },
        )
        if video_resp:
            video_url = video_resp.get("videoUrl", "")
            if video_url:
                streams.append({
                    "url": video_url,
                    "quality": "1080p",
                    "provider": "CastleTV",
                    "format": "hls",
                })

    return streams
