"""Celery application used by the AI worker container.

The Celery task is a thin wrapper: it delegates to the same ``runner.process_job``
used by the polling worker so both dispatch paths share one code path.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
for path in (REPO_ROOT / "apps" / "api", REPO_ROOT / "ai-engine"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.core.config import settings  # noqa: E402
from celery import Celery  # noqa: E402

logger = logging.getLogger("roadguard.worker.celery")

celery_app = Celery("roadguard", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=settings.job_lease_seconds,
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
)


@celery_app.task(name="roadguard.process_video_job", bind=True, max_retries=0)
def process_video_job(self, job_id: str) -> dict:  # noqa: ANN001
    from ai_engine.workers.runner import process_job

    logger.info("celery_job_received job=%s", job_id)
    return process_job(job_id)


if __name__ == "__main__":  # pragma: no cover - container entrypoint
    celery_app.start()
