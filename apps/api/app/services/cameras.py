"""Camera registry and health.

Credentials are represented by an opaque secret reference only. No API response,
log line or error message ever contains a stream URL, username or password.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.audit import record_audit
from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.models import Camera, CameraConnectionStatus, CameraSourceType, LiveSessionStatus, LiveStreamSession
from app.services.events import publish_event
from app.services.geo import set_point
from sqlalchemy import select
from sqlalchemy.orm import Session


def create_camera(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_label: str,
    payload: object,
    request_id: str | None,
) -> Camera:
    data = payload
    duplicate = session.execute(
        select(Camera).where(
            Camera.organization_id == organization_id, Camera.camera_code == data.camera_code
        )
    ).scalar_one_or_none()
    if duplicate:
        raise Conflict("A camera with this code already exists.", code="DUPLICATE_CAMERA_CODE")
    if data.source_type == CameraSourceType.RTSP and not settings.live_cctv_enabled:
        raise ValidationError(
            "Live RTSP cameras are disabled on this deployment. "
            "Register the camera with source_type upload_association or demo_replay.",
            code="LIVE_INGEST_DISABLED",
        )

    camera = Camera(
        organization_id=organization_id,
        camera_code=data.camera_code.strip(),
        name=data.name.strip(),
        description=data.description,
        source_type=data.source_type,
        is_enabled=data.is_enabled,
        secret_reference=data.secret_reference,
        connection_status=CameraConnectionStatus.UNKNOWN,
        is_demo=settings.demo_mode,
    )
    if data.location is not None:
        set_point(camera, data.location.latitude, data.location.longitude, data.location.quality)
    session.add(camera)
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action="camera.created",
        entity_type="camera",
        entity_id=camera.id,
        request_id=request_id,
        summary=f"Camera {camera.camera_code} registered.",
        metadata={"source_type": camera.source_type.value},
    )
    return camera


def update_camera(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_label: str,
    camera_id: uuid.UUID,
    payload: object,
    request_id: str | None,
) -> Camera:
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise NotFound("Camera not found.")
    data = payload
    if data.name is not None:
        camera.name = data.name.strip()
    if data.description is not None:
        camera.description = data.description
    if data.is_enabled is not None:
        camera.is_enabled = data.is_enabled
    if data.location is not None:
        set_point(camera, data.location.latitude, data.location.longitude, data.location.quality)
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action="camera.updated",
        entity_type="camera",
        entity_id=camera.id,
        request_id=request_id,
        summary=f"Camera {camera.camera_code} updated.",
    )
    return camera


def set_enabled(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_label: str,
    camera_id: uuid.UUID,
    enabled: bool,
    request_id: str | None,
) -> Camera:
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise NotFound("Camera not found.")
    if camera.source_type == CameraSourceType.RTSP and enabled and not settings.live_cctv_enabled:
        raise ValidationError(
            "Live ingestion is disabled on this deployment.", code="LIVE_INGEST_DISABLED"
        )
    camera.is_enabled = enabled
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action="camera.enabled" if enabled else "camera.disabled",
        entity_type="camera",
        entity_id=camera.id,
        request_id=request_id,
        summary=f"Camera {camera.camera_code} {'enabled' if enabled else 'disabled'}.",
    )
    publish_event(
        organization_id=organization_id,
        event_type="camera.status_changed",
        resource_type="camera",
        resource_id=camera.id,
        data={"camera_id": str(camera.id), "is_enabled": enabled},
    )
    return camera


def health(session: Session, camera_id: uuid.UUID) -> dict[str, object]:
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise NotFound("Camera not found.")
    live = session.execute(
        select(LiveStreamSession)
        .where(LiveStreamSession.camera_id == camera.id)
        .order_by(LiveStreamSession.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    detail = None
    if camera.source_type == CameraSourceType.RTSP and not settings.live_cctv_enabled:
        detail = "Live ingestion is disabled on this deployment."
    return {
        "camera_id": camera.id,
        "connection_status": camera.connection_status,
        "is_simulated": camera.source_type != CameraSourceType.RTSP,
        "last_seen_at": camera.last_seen_at,
        "detail": detail,
        "live_enabled": settings.live_cctv_enabled,
        "active_session_status": live.status if live else None,
    }


def start_simulated_session(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_label: str,
    camera_id: uuid.UUID,
    confirmed: bool,
    request_id: str | None,
) -> LiveStreamSession:
    """Start a clearly labelled SIMULATED LIVE replay session.

    A real RTSP connection is never opened from the API process: it requires an
    authorized deployment, an allowlisted host and a server-side secret, and is
    reported as blocked here rather than faked.
    """
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise NotFound("Camera not found.")
    if not confirmed:
        raise ValidationError(
            "Confirm that you understand this feed is simulated, not a live camera.",
            code="SIMULATION_CONFIRMATION_REQUIRED",
        )
    if camera.source_type == CameraSourceType.RTSP:
        if not settings.live_cctv_enabled:
            status = LiveSessionStatus.BLOCKED
            detail = (
                "Live RTSP ingestion is disabled. Set LIVE_CCTV_ENABLED=true and configure an "
                "authorized allowlist before connecting a real camera."
            )
        else:
            status = LiveSessionStatus.BLOCKED
            detail = (
                "RTSP connector requires an authorized deployment with network access to the "
                "allowlisted camera host. No connection was attempted from this prototype."
            )
        live = LiveStreamSession(
            organization_id=organization_id,
            camera_id=camera.id,
            status=status,
            mode="rtsp",
            is_simulated=False,
            started_by=actor_id,
            detail=detail,
        )
        session.add(live)
        session.flush()
        record_audit(
            session,
            organization_id=organization_id,
            actor_id=actor_id,
            actor_label=actor_label,
            action="camera.live_session_blocked",
            entity_type="camera",
            entity_id=camera.id,
            request_id=request_id,
            summary="Live session request blocked by policy.",
        )
        return live

    live = LiveStreamSession(
        organization_id=organization_id,
        camera_id=camera.id,
        status=LiveSessionStatus.SIMULATED,
        mode="demo_replay",
        is_simulated=True,
        started_at=datetime.now(UTC),
        started_by=actor_id,
        detail="Simulated live replay of a stored demonstration clip.",
    )
    session.add(live)
    camera.connection_status = CameraConnectionStatus.SIMULATED
    camera.last_seen_at = datetime.now(UTC)
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action="camera.simulated_live_started",
        entity_type="camera",
        entity_id=camera.id,
        request_id=request_id,
        summary="Simulated live session started.",
    )
    publish_event(
        organization_id=organization_id,
        event_type="camera.status_changed",
        resource_type="camera",
        resource_id=camera.id,
        data={"camera_id": str(camera.id), "status": CameraConnectionStatus.SIMULATED.value},
    )
    return live
def start_rtsp_live_session(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_label: str,
    camera_id: uuid.UUID,
    confirmed: bool,
    request_id: str | None,
) -> LiveStreamSession:
    """Start a live RTSP session for an authorized camera.

    This function is only called when LIVE_CCTV_ENABLED=true and the camera
    host is in the allowlist. It validates authorization and creates a
    LiveStreamSession with CONNECTED status. The actual frame ingestion
    is handled by the worker via the RTSP adapter.
    """
    from ai_engine.video.rtsp_adapter import (
        check_rtsp_authorization,
        resolve_rtsp_secret,
    )

    camera = session.get(Camera, camera_id)
    if camera is None:
        raise NotFound("Camera not found.")
    if camera.source_type != CameraSourceType.RTSP:
        raise ValidationError("Camera is not configured for RTSP.", code="INVALID_SOURCE_TYPE")
    if not confirmed:
        raise ValidationError(
            "Confirm that you are authorized to connect to this live camera feed.",
            code="RTSP_CONFIRMATION_REQUIRED",
        )
    if not camera.secret_reference:
        raise ValidationError(
            "Camera has no secret reference configured. Cannot connect to RTSP stream.",
            code="MISSING_SECRET_REFERENCE",
        )

    # Resolve credentials to get host for authorization check
    try:
        credentials = resolve_rtsp_secret(camera.secret_reference)
    except Exception as e:
        raise ValidationError(f"Failed to resolve RTSP credentials: {e}", code="SECRET_RESOLUTION_FAILED") from e

    host = credentials.get("host")
    if not host:
        raise ValidationError("RTSP secret must contain 'host' field.", code="INVALID_SECRET_FORMAT")

    cidr = credentials.get("cidr")

    # Authorization check (host allowlist, CIDR allowlist, LIVE_CCTV_ENABLED)
    try:
        check_rtsp_authorization(host, cidr)
    except Exception as e:
        raise ValidationError(str(e), code="RTSP_AUTHORIZATION_FAILED") from e

    # If we get here, RTSP is authorized. Create a CONNECTED session.
    live = LiveStreamSession(
        organization_id=organization_id,
        camera_id=camera.id,
        status=LiveSessionStatus.CONNECTED,
        mode="rtsp",
        is_simulated=False,
        started_at=datetime.now(UTC),
        started_by=actor_id,
        detail=f"RTSP stream from {credentials.get('host')} - frame ingestion handled by worker",
    )
    session.add(live)
    camera.connection_status = CameraConnectionStatus.CONNECTED
    camera.last_seen_at = datetime.now(UTC)
    session.flush()

    record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action="camera.rtsp_live_started",
        entity_type="camera",
        entity_id=camera.id,
        request_id=request_id,
        summary=f"Authorized RTSP live session started for {camera.camera_code}.",
        metadata={"host": credentials.get("host"), "mode": "rtsp"},
    )

    publish_event(
        organization_id=organization_id,
        event_type="camera.status_changed",
        resource_type="camera",
        resource_id=camera.id,
        data={"camera_id": str(camera.id), "status": CameraConnectionStatus.CONNECTED.value},
    )

    return live


def stop_live_session(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_label: str,
    camera_id: uuid.UUID,
    request_id: str | None,
) -> LiveStreamSession:
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise NotFound("Camera not found.")
    live = session.execute(
        select(LiveStreamSession)
        .where(
            LiveStreamSession.camera_id == camera.id,
            LiveStreamSession.status.in_(
                [LiveSessionStatus.SIMULATED, LiveSessionStatus.CONNECTED, LiveSessionStatus.DISCONNECTED]
            ),
        )
        .order_by(LiveStreamSession.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if live is None:
        raise Conflict("No active live session for this camera.", code="NO_ACTIVE_SESSION")
    live.status = LiveSessionStatus.STOPPED
    live.stopped_at = datetime.now(UTC)
    camera.connection_status = CameraConnectionStatus.OFFLINE
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action="camera.live_session_stopped",
        entity_type="camera",
        entity_id=camera.id,
        request_id=request_id,
        summary="Live/simulated session stopped.",
    )
    return live
