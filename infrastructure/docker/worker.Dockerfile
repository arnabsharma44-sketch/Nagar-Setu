FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/api:/app/ai-engine \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ffmpeg is required by the video decoder; libgl/libglib support headless OpenCV.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libpq5 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt /tmp/api-requirements.txt
COPY ai-engine/requirements.txt /tmp/engine-requirements.txt
RUN pip install --no-cache-dir -r /tmp/api-requirements.txt -r /tmp/engine-requirements.txt

COPY apps/api /app/apps/api
COPY ai-engine /app/ai-engine
COPY scripts /app/scripts
COPY shared /app/shared

RUN useradd --create-home --uid 10002 roadguard \
    && mkdir -p /app/storage /app/datasets \
    && chown -R roadguard:roadguard /app
USER roadguard

WORKDIR /app

CMD ["celery", "-A", "ai_engine.workers.celery_app:celery_app", "worker", "--loglevel=INFO", "--concurrency=1", "--pool=solo"]
