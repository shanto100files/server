import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from curl_cffi import requests as cffi_requests

app = FastAPI(title="CinePix Local Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/proxy")
def proxy_url(url: str, referer: str = None):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"}
        if referer:
            headers["Referer"] = referer
            
        r = cffi_requests.get(
            url, 
            impersonate="chrome", 
            headers=headers, 
            timeout=15,
            allow_redirects=True
        )
        return HTMLResponse(content=r.text, status_code=r.status_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8081))
    print(f"🚀 CinePix Local Proxy running at http://localhost:{port}")
    uvicorn.run("termux-proxy:app", host="0.0.0.0", port=port, log_level="warning")
