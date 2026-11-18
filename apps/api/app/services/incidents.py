"""Incident review workflow and incident analytics."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.deps import RequestContext
from app.core.audit import record_audit
from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.models import (
    AccidentRecord,
    Camera,
    Evidence,
    Incident,
    IncidentSourceKind,
    IncidentType,
    ReviewDecision,
    ReviewStatus,
    Severity,
)
from app.schemas.domain import IncidentAnalytics, IncidentReviewRequest, ManualIncidentRequest
from app.services.events import publish_event
from app.services.geo import set_point
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def list_incidents(
    session: Session,
    *,
    review_status: ReviewStatus | None = None,
    incident_type: IncidentType | None = None,
    source_kind: IncidentSourceKind | None = None,
    camera_id: uuid.UUID | None = None,
    video_id: uuid.UUID | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[Incident], int]:
    stmt = select(Incident)
    count_stmt = select(func.count()).select_from(Incident)
    filters = []
    if review_status:
        filters.append(Incident.review_status == review_status)
    if incident_type:
        filters.append(Incident.incident_type == incident_type)
    if source_kind:
        filters.append(Incident.source_kind == source_kind)
    if camera_id:
        filters.append(Incident.camera_id == camera_id)
    if video_id:
        filters.append(Incident.video_id == video_id)
    for condition in filters:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    stmt = stmt.order_by(Incident.event_time.desc()).limit(limit).offset(offset)
    total = int(session.execute(count_stmt).scalar_one())
    return list(session.execute(stmt).scalars().all()), total


def get_incident(session: Session, incident_id: uuid.UUID) -> Incident:
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise NotFound("Incident not found.")
    return incident


def camera_code_map(session: Session, camera_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not camera_ids:
        return {}
    rows = session.execute(
        select(Camera.id, Camera.camera_code).where(Camera.id.in_(camera_ids))
    ).all()
    return {camera_id: code for camera_id, code in rows}


def evidence_for_incident(session: Session, incident_id: uuid.UUID) -> list[Evidence]:
    return list(
        session.execute(
            select(Evidence)
            .where(Evidence.incident_id == incident_id)
            .order_by(Evidence.created_at)
        ).scalars()
    )


def review_incident(
    ctx: RequestContext, incident_id: uuid.UUID, payload: IncidentReviewRequest
) -> Incident:
    ctx.require("incident:review")
    incident = get_incident(ctx.session, incident_id)
    if incident.review_status == ReviewStatus(payload.decision.value):
        raise Conflict("This incident already has the requested review status.", code="NO_CHANGE")
    if payload.decision != ReviewDecision.CONFIRMED and not payload.notes:
        raise ValidationError(
            "A short note is required when rejecting or requesting more information.",
            code="REVIEW_NOTE_REQUIRED",
        )

    previous = incident.review_status
    incident.review_status = ReviewStatus(payload.decision.value)
    incident.reviewed_by = ctx.user_id
    incident.reviewed_at = datetime.now(UTC)
    incident.review_notes = payload.notes
    ctx.session.flush()

    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="incident.reviewed",
        entity_type="incident",
        entity_id=incident.id,
        request_id=ctx.request_id,
        summary=f"Review decision: {incident.review_status.value}.",
        metadata={
            "from": previous.value,
            "to": incident.review_status.value,
            "notes": payload.notes,
        },
    )
    publish_event(
        organization_id=ctx.organization_id,
        event_type="incident.reviewed",
        resource_type="incident",
        resource_id=incident.id,
        data={
            "incident_id": str(incident.id),
            "review_status": incident.review_status.value,
        },
    )
    return incident


def create_manual_incident(ctx: RequestContext, payload: ManualIncidentRequest) -> Incident:
    ctx.require("incident:create")
    camera: Camera | None = None
    if payload.camera_id is not None:
        camera = ctx.session.get(Camera, payload.camera_id)
        if camera is None:
            raise NotFound("Camera not found.")

    incident = Incident(
        organization_id=ctx.organization_id,
        camera_id=camera.id if camera else None,
        incident_type=payload.incident_type,
        source_kind=IncidentSourceKind.MANUAL_OBSERVATION,
        severity=payload.severity or Severity.MEDIUM,
        event_time=payload.event_time,
        description=payload.description,
        review_status=ReviewStatus.PENDING,
        limitations=["RECORDED_BY_A_HUMAN_OBSERVER"],
        is_demo=settings.demo_mode,
    )
    if payload.location is not None:
        set_point(
            incident, payload.location.latitude, payload.location.longitude, payload.location.quality
        )
    elif camera is not None and camera.latitude is not None:
        set_point(incident, camera.latitude, camera.longitude, camera.location_quality)
    ctx.session.add(incident)
    ctx.session.flush()
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="incident.manual_observation_created",
        entity_type="incident",
        entity_id=incident.id,
        request_id=ctx.request_id,
        summary="Manual road-safety observation recorded.",
    )
    return incident


def incident_analytics(
    session: Session,
    *,
    window_from: datetime | None,
    window_to: datetime | None,
) -> IncidentAnalytics:
    incident_filters = []
    if window_from:
        incident_filters.append(Incident.event_time >= window_from)
    if window_to:
        incident_filters.append(Incident.event_time <= window_to)

    status_rows = session.execute(
        select(Incident.review_status, func.count())
        .where(*incident_filters)
        .group_by(Incident.review_status)
    ).all()
    type_rows = session.execute(
        select(Incident.incident_type, func.count())
        .where(*incident_filters)
        .group_by(Incident.incident_type)
    ).all()
    kind_rows = session.execute(
        select(Incident.source_kind, func.count())
        .where(*incident_filters)
        .group_by(Incident.source_kind)
    ).all()

    accident_filters = []
    if window_from:
        accident_filters.append(AccidentRecord.accident_time >= window_from)
    if window_to:
        accident_filters.append(AccidentRecord.accident_time <= window_to)
    accidents = int(
        session.execute(
            select(func.count()).select_from(AccidentRecord).where(*accident_filters)
        ).scalar_one()
    )

    by_status = {status.value: int(count) for status, count in status_rows}
    by_type = {incident_type.value: int(count) for incident_type, count in type_rows}
    by_kind = {kind.value: int(count) for kind, count in kind_rows}

    return IncidentAnalytics(
        window_from=window_from,
        window_to=window_to,
        total=sum(by_status.values()),
        by_review_status=by_status,
        by_type=by_type,
        by_source_kind=by_kind,
        confirmed_observations=by_status.get(ReviewStatus.CONFIRMED.value, 0),
        pending_candidates=by_status.get(ReviewStatus.PENDING.value, 0),
        historical_accidents_in_window=accidents,
        data_note=(
            "AI candidate events and imported historical accident records are counted "
            "separately and must not be added together as one accident count."
        ),
    )
