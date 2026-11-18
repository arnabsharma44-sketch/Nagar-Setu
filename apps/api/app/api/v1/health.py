"""Liveness, readiness and bootstrap metadata endpoints."""

from __future__ import annotations

import logging

from app.api.deps import CurrentContext, RequestContext
from app.core.config import settings
from app.core.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS
from app.db.session import get_app_engine
from app.schemas.common import Envelope, ok
from app.schemas.domain import BootstrapMeta
from app.services.storage import get_storage
from fastapi import APIRouter, Request
from sqlalchemy import text

logger = logging.getLogger("roadguard.health")

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=Envelope[dict])
def live(request: Request) -> Envelope[dict]:
    return ok({"status": "ok", "service": "roadguard-api", "version": "1.0.0"}, request)


@router.get("/health/ready", response_model=Envelope[dict])
def ready(request: Request) -> Envelope[dict]:
    checks: dict[str, str] = {}
    status = "ok"

    try:
        with get_app_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"unavailable:{type(exc).__name__}"
        status = "degraded"

    try:
        stat = get_storage().stat("__readiness_probe__")
        checks["storage"] = "ok" if stat.exists is False else "ok"
    except Exception as exc:
        checks["storage"] = f"unavailable:{type(exc).__name__}"
        status = "degraded"

    checks["llm"] = "configured" if settings.llm_provider != "none" else "disabled"
    checks["live_cctv"] = "enabled" if settings.live_cctv_enabled else "disabled"
    return ok({"status": status, "checks": checks}, request)


@router.get("/meta/bootstrap", response_model=Envelope[BootstrapMeta])
def bootstrap(request: Request, ctx: RequestContext = CurrentContext) -> Envelope[BootstrapMeta]:
    payload = BootstrapMeta(
        environment=settings.environment,
        demo_mode=settings.demo_mode,
        permissions=sorted(ctx.principal.permissions),
        roles=sorted(ROLE_PERMISSIONS),
        max_upload_bytes=settings.max_upload_bytes,
        max_video_duration_seconds=settings.max_video_duration_seconds,
        supported_content_types=sorted(settings.supported_video_content_types),
        live_cctv_enabled=settings.live_cctv_enabled,
        llm_enabled=settings.llm_provider != "none" and bool(settings.openai_api_key),
        detector_backend=settings.detector_backend,
    )
    return ok(payload, request)


@router.get("/meta/permissions", response_model=Envelope[dict])
def permissions(request: Request) -> Envelope[dict]:
    return ok(
        {
            "all": sorted(ALL_PERMISSIONS),
            "roles": {role: sorted(values) for role, values in ROLE_PERMISSIONS.items()},
        },
        request,
    )
