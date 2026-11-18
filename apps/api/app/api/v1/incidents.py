"""Incident queue, detail, review and manual observations."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.api.deps import CurrentContext, RequestContext
from app.core.errors import NotFound
from app.models import Incident, IncidentSourceKind, IncidentType, ReviewStatus
from app.schemas.common import Envelope, ok, paginate
from app.schemas.domain import (
    EvidenceOut,
    IncidentAnalytics,
    IncidentOut,
    IncidentReviewRequest,
    ManualIncidentRequest,
)
from app.schemas.serializers import evidence_out, incident_out
from app.services import incidents as incident_service
from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("/analytics", response_model=Envelope[IncidentAnalytics])
def analytics(
    request: Request,
    window_from: datetime | None = Query(default=None),
    window_to: datetime | None = Query(default=None),
    ctx: RequestContext = CurrentContext,
) -> Envelope[IncidentAnalytics]:
    ctx.require("analytics:read")
    payload = incident_service.incident_analytics(
        ctx.session, window_from=window_from, window_to=window_to
    )
    return ok(payload, request)


@router.get("", response_model=Envelope[list[IncidentOut]])
def list_incidents(
    request: Request,
    review_status: ReviewStatus | None = Query(default=None),
    incident_type: IncidentType | None = Query(default=None),
    source_kind: IncidentSourceKind | None = Query(default=None),
    camera_id: uuid.UUID | None = Query(default=None),
    video_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[IncidentOut]]:
    ctx.require("incident:read")
    rows, total = incident_service.list_incidents(
        ctx.session,
        review_status=review_status,
        incident_type=incident_type,
        source_kind=source_kind,
        camera_id=camera_id,
        video_id=video_id,
        limit=limit,
        offset=offset,
    )
    codes = incident_service.camera_code_map(
        ctx.session, [row.camera_id for row in rows if row.camera_id]
    )
    payload = [
        incident_out(row, camera_code=codes.get(row.camera_id) if row.camera_id else None)
        for row in rows
    ]
    return ok(payload, request, pagination=paginate(limit, offset, total))


@router.post("/manual", response_model=Envelope[IncidentOut], status_code=201)
def create_manual_incident(
    payload: ManualIncidentRequest, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[IncidentOut]:
    incident = incident_service.create_manual_incident(ctx, payload)
    codes = incident_service.camera_code_map(
        ctx.session, [incident.camera_id] if incident.camera_id else []
    )
    return ok(
        incident_out(
            incident, camera_code=codes.get(incident.camera_id) if incident.camera_id else None
        ),
        request,
    )


@router.get("/{incident_id}", response_model=Envelope[IncidentOut])
def get_incident(
    incident_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[IncidentOut]:
    ctx.require("incident:read")
    incident = ctx.session.get(Incident, incident_id)
    if incident is None:
        raise NotFound("Incident not found.")
    codes = incident_service.camera_code_map(
        ctx.session, [incident.camera_id] if incident.camera_id else []
    )
    return ok(
        incident_out(
            incident, camera_code=codes.get(incident.camera_id) if incident.camera_id else None
        ),
        request,
    )


@router.get("/{incident_id}/evidence", response_model=Envelope[list[EvidenceOut]])
def incident_evidence(
    incident_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[list[EvidenceOut]]:
    ctx.require("evidence:read")
    incident = ctx.session.get(Incident, incident_id)
    if incident is None:
        raise NotFound("Incident not found.")
    rows = incident_service.evidence_for_incident(ctx.session, incident.id)
    return ok([evidence_out(row) for row in rows], request)


@router.patch("/{incident_id}/review", response_model=Envelope[IncidentOut])
def review_incident(
    incident_id: uuid.UUID,
    payload: IncidentReviewRequest,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[IncidentOut]:
    incident = incident_service.review_incident(ctx, incident_id, payload)
    codes = incident_service.camera_code_map(
        ctx.session, [incident.camera_id] if incident.camera_id else []
    )
    return ok(
        incident_out(
            incident, camera_code=codes.get(incident.camera_id) if incident.camera_id else None
        ),
        request,
    )
