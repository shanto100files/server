FROM python:3.12-slim

# Create a non-root user for HuggingFace Spaces compatibility
RUN useradd -m -u 1000 user

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R user:user /app

# Switch to the non-root user
USER user

ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV CLOUDSCRAPER_INSTALLED=1

EXPOSE $PORT

CMD uvicorn server:app --host 0.0.0.0 --port $PORT --workers 1 --limit-concurrency 100 --timeout-keep-alive 60