"""ROADGUARD AI — FastAPI application."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
AI_ENGINE_DIR = REPO_ROOT / "ai-engine"
for path in (REPO_ROOT, AI_ENGINE_DIR):
    if path.is_dir() and str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.api.v1 import api_router  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.errors import register_exception_handlers  # noqa: E402
from app.middleware.http import RequestContextMiddleware  # noqa: E402

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("roadguard.api")

DESCRIPTION = """
ROADGUARD AI — AI-assisted road-safety investigation and corrective-action tracking.

Every AI output is a **candidate observation** requiring human review. Responsibility
matching returns recorded relationships only; the platform never determines legal
liability.
"""


def create_app() -> FastAPI:
    app = FastAPI(
        title="ROADGUARD AI API",
        version="1.0.0",
        description=DESCRIPTION,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["content-type", "x-csrf-token", "authorization", "x-request-id"],
        expose_headers=["x-request-id"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> JSONResponse:
        return JSONResponse(
            {
                "service": "roadguard-api",
                "version": "1.0.0",
                "api": settings.api_prefix,
                "docs": "/docs",
                "disclaimer": (
                    "Prototype for authorized demonstration use with synthetic data. "
                    "AI outputs are candidate observations, not confirmed accidents."
                ),
            }
        )

    @app.on_event("startup")
    def _startup() -> None:
        settings.require_runtime_secrets()
        logger.info(
            "api_started env=%s storage=%s runner=%s detector=%s",
            settings.environment,
            settings.storage_backend,
            settings.job_runner,
            settings.detector_backend,
        )

    return app


app = create_app()
