FROM python:3.12-slim

# Create a non-root user for HuggingFace Spaces compatibility
RUN useradd -m -u 1000 user

WORKDIR /app

# Install WARP proxy dependencies + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev curl gnupg2 iptables net-tools \
    && curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ bookworm main" > /etc/apt/sources.list.d/cloudflare-client.list \
    && apt-get update && apt-get install -y --no-install-recommends cloudflare-warp \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Register WARP (free tier, no account needed for basic use)
# WARP needs root for WireGuard interface, so keep root user
RUN mkdir -p /var/lib/cloudflare-warp && \
    warp-cli registration new 2>/dev/null || true && \
    warp-cli mode proxy 2>/dev/null || true && \
    warp-cli proxy port 40000 2>/dev/null || true && \
    warp-cli connect 2>/dev/null || true

COPY . .
RUN chown -R user:user /app

ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV CLOUDSCRAPER_INSTALLED=1
ENV WARP_PROXY_URL=socks5://127.0.0.1:40000

EXPOSE $PORT

CMD bash -c "warp-cli connect 2>/dev/null; sleep 2; uvicorn server:app --host 0.0.0.0 --port $PORT --workers 1 --limit-concurrency 100 --timeout-keep-alive 60"