"""In-repo claim/lease worker.

Runs the same pipeline as the Celery task without requiring Redis, which keeps the
prototype demonstrable on a laptop while preserving the rule that long-running
inference never happens inside an API request.

Usage::

    python -m ai_engine.workers.polling_worker --once
    python -m ai_engine.workers.polling_worker --loop --interval 2
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
for path in (REPO_ROOT / "apps" / "api", REPO_ROOT / "ai-engine"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ai_engine.workers.runner import claim_next_job, process_job  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.session import dispose_engines  # noqa: E402

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("roadguard.worker.polling")

_shutdown = {"requested": False}


def _handle_signal(signum, frame):  # noqa: ANN001, ARG001
    logger.info("shutdown requested signal=%s", signum)
    _shutdown["requested"] = True


def worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


def run_once(identifier: str) -> bool:
    claimed = claim_next_job(identifier)
    if claimed is None:
        return False
    job_id, organization_id = claimed
    logger.info("job_claimed job=%s organization=%s", job_id, organization_id)
    result = process_job(job_id)
    logger.info("job_finished job=%s result=%s", job_id, result.get("status"))
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ROADGUARD AI polling worker")
    parser.add_argument("--once", action="store_true", help="process at most one available job")
    parser.add_argument("--loop", action="store_true", help="keep polling for jobs")
    parser.add_argument("--interval", type=float, default=2.0, help="idle poll interval in seconds")
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    identifier = worker_id()
    logger.info("worker_started id=%s runner=%s", identifier, settings.job_runner)

    processed = 0
    try:
        while not _shutdown["requested"]:
            did_work = run_once(identifier)
            if did_work:
                processed += 1
                if args.once:
                    break
                continue
            if args.once or not args.loop:
                break
            time.sleep(max(0.2, args.interval))
    finally:
        dispose_engines()
        logger.info("worker_stopped processed=%s", processed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
