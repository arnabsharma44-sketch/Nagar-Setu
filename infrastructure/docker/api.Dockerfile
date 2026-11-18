FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/api:/app/ai-engine \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt /tmp/api-requirements.txt
COPY ai-engine/requirements.txt /tmp/engine-requirements.txt
RUN pip install --no-cache-dir -r /tmp/api-requirements.txt -r /tmp/engine-requirements.txt

COPY apps/api /app/apps/api
COPY ai-engine /app/ai-engine
COPY scripts /app/scripts
COPY shared /app/shared

RUN useradd --create-home --uid 10001 roadguard \
    && mkdir -p /app/storage \
    && chown -R roadguard:roadguard /app
USER roadguard

WORKDIR /app/apps/api
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=10 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
