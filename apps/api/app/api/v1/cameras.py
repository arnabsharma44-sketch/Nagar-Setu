"""Camera registry, health and simulated-live endpoints."""

from __future__ import annotations

import uuid

from app.api.deps import CurrentContext, RequestContext
from app.core.errors import NotFound
from app.models import Camera
from app.schemas.common import Envelope, ok, paginate
from app.schemas.domain import (
    CameraCreate,
    CameraHealthOut,
    CameraOut,
    CameraUpdate,
    StepUpRequest,
)
from app.schemas.serializers import camera_out
from app.services import cameras as camera_service
from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("", response_model=Envelope[list[CameraOut]])
def list_cameras(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[CameraOut]]:
    ctx.require("camera:read")
    total = int(
        ctx.session.execute(select(func.count()).select_from(Camera)).scalar_one()
    )
    rows = ctx.session.execute(
        select(Camera).order_by(Camera.camera_code).limit(limit).offset(offset)
    ).scalars()
    return ok([camera_out(camera) for camera in rows], request, pagination=paginate(limit, offset, total))


@router.post("", response_model=Envelope[CameraOut], status_code=201)
def create_camera(
    payload: CameraCreate, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[CameraOut]:
    ctx.require("camera:manage")
    camera = camera_service.create_camera(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        payload=payload,
        request_id=ctx.request_id,
    )
    return ok(camera_out(camera), request)


@router.get("/{camera_id}", response_model=Envelope[CameraOut])
def get_camera(
    camera_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[CameraOut]:
    ctx.require("camera:read")
    camera = ctx.session.get(Camera, camera_id)
    if camera is None:
        raise NotFound("Camera not found.")
    return ok(camera_out(camera), request)


@router.patch("/{camera_id}", response_model=Envelope[CameraOut])
def update_camera(
    camera_id: uuid.UUID,
    payload: CameraUpdate,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[CameraOut]:
    ctx.require("camera:manage")
    camera = camera_service.update_camera(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        camera_id=camera_id,
        payload=payload,
        request_id=ctx.request_id,
    )
    return ok(camera_out(camera), request)


@router.post("/{camera_id}/enable", response_model=Envelope[CameraOut])
def enable_camera(
    camera_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[CameraOut]:
    ctx.require("camera:manage")
    camera = camera_service.set_enabled(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        camera_id=camera_id,
        enabled=True,
        request_id=ctx.request_id,
    )
    return ok(camera_out(camera), request)


@router.post("/{camera_id}/disable", response_model=Envelope[CameraOut])
def disable_camera(
    camera_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[CameraOut]:
    ctx.require("camera:manage")
    camera = camera_service.set_enabled(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        camera_id=camera_id,
        enabled=False,
        request_id=ctx.request_id,
    )
    return ok(camera_out(camera), request)


@router.get("/{camera_id}/health", response_model=Envelope[CameraHealthOut])
def camera_health(
    camera_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[CameraHealthOut]:
    ctx.require("camera:read")
    payload = camera_service.health(ctx.session, camera_id)
    return ok(CameraHealthOut(**payload), request)


@router.post("/{camera_id}/live/simulate", response_model=Envelope[dict])
def start_simulated_live(
    camera_id: uuid.UUID,
    payload: StepUpRequest,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[dict]:
    ctx.require("camera:manage")
    session_row = camera_service.start_simulated_session(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        camera_id=camera_id,
        confirmed=payload.confirm,
        request_id=ctx.request_id,
    )
    return ok(
        {
            "session_id": str(session_row.id),
            "status": session_row.status.value,
            "is_simulated": session_row.is_simulated,
            "mode": session_row.mode,
            "detail": session_row.detail,
        },
        request,
    )


@router.post("/{camera_id}/live/rtsp", response_model=Envelope[dict])
def start_rtsp_live(
    camera_id: uuid.UUID,
    payload: StepUpRequest,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[dict]:
    ctx.require("camera:manage")
    session_row = camera_service.start_rtsp_live_session(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        camera_id=camera_id,
        confirmed=payload.confirm,
        request_id=ctx.request_id,
    )
    return ok(
        {
            "session_id": str(session_row.id),
            "status": session_row.status.value,
            "is_simulated": session_row.is_simulated,
            "mode": session_row.mode,
            "detail": session_row.detail,
        },
        request,
    )


@router.post("/{camera_id}/live/stop", response_model=Envelope[dict])
def stop_live(
    camera_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[dict]:
    ctx.require("camera:manage")
    session_row = camera_service.stop_live_session(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        camera_id=camera_id,
        request_id=ctx.request_id,
    )
    return ok({"session_id": str(session_row.id), "status": session_row.status.value}, request)
