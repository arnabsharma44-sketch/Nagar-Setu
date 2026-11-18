"""Investigation cases, draft analysis and recommendations."""

from __future__ import annotations

import uuid

from app.api.deps import CurrentContext, RequestContext
from app.models import (
    Asset,
    Department,
    Evidence,
    Incident,
    Investigation,
    Recommendation,
    WorkOrder,
)
from app.schemas.common import Envelope, ok, paginate
from app.schemas.domain import (
    AssetOut,
    EvidenceOut,
    IncidentOut,
    InvestigationAnalysis,
    InvestigationAssign,
    InvestigationCreate,
    InvestigationOut,
    InvestigationUpdate,
    NearbyAsset,
    RecommendationCreate,
    RecommendationOut,
    RecommendationReview,
    ResponsibilityResponse,
    WorkOrderOut,
)
from app.schemas.serializers import (
    asset_out,
    evidence_out,
    incident_out,
    investigation_out,
    recommendation_out,
    work_order_out,
)
from app.services import investigations as investigation_service
from app.services import registry as registry_service
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

router = APIRouter(tags=["investigations"])


class InvestigationDetail(BaseModel):
    investigation: InvestigationOut
    incident: IncidentOut | None = None
    incident_evidence: list[EvidenceOut] = []
    asset: AssetOut | None = None
    nearby_assets: list[NearbyAsset] = []
    responsibility: ResponsibilityResponse | None = None
    recommendations: list[RecommendationOut] = []
    work_orders: list[WorkOrderOut] = []
    evidence: list[EvidenceOut] = []
    source_records: list[str] = []
    disclaimer: str


@router.get("/investigations", response_model=Envelope[list[InvestigationOut]])
def list_investigations(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[InvestigationOut]]:
    ctx.require("investigation:read")
    total = int(ctx.session.execute(select(func.count()).select_from(Investigation)).scalar_one())
    rows = ctx.session.execute(
        select(Investigation)
        .order_by(Investigation.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars()
    return ok(
        [investigation_out(row) for row in rows], request, pagination=paginate(limit, offset, total)
    )


@router.post("/investigations", response_model=Envelope[InvestigationOut], status_code=201)
def create_investigation(
    payload: InvestigationCreate, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[InvestigationOut]:
    investigation = investigation_service.create_investigation(ctx, payload)
    return ok(investigation_out(investigation), request)


@router.get("/investigations/{investigation_id}", response_model=Envelope[InvestigationDetail])
def get_investigation(
    investigation_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[InvestigationDetail]:
    ctx.require("investigation:read")
    investigation = investigation_service.get_investigation(ctx.session, investigation_id)

    incident = (
        ctx.session.get(Incident, investigation.incident_id) if investigation.incident_id else None
    )
    asset = ctx.session.get(Asset, investigation.asset_id) if investigation.asset_id else None
    incident_evidence = (
        list(
            ctx.session.execute(
                select(Evidence).where(Evidence.incident_id == incident.id)
            ).scalars()
        )
        if incident
        else []
    )
    nearby: list[NearbyAsset] = []
    responsibility: ResponsibilityResponse | None = None
    if asset is not None:
        event_date = incident.event_time.date() if incident else None
        responsibility = registry_service.build_responsibility(
            ctx.session, asset=asset, event_date=event_date
        )
        if asset.latitude is not None and asset.longitude is not None:
            nearby = registry_service.nearby_assets(
                ctx.session,
                latitude=asset.latitude,
                longitude=asset.longitude,
                radius_meters=500,
                limit=5,
            )
    recommendations = list(
        ctx.session.execute(
            select(Recommendation)
            .where(Recommendation.investigation_id == investigation.id)
            .order_by(Recommendation.created_at)
        ).scalars()
    )
    work_orders = list(
        ctx.session.execute(
            select(WorkOrder)
            .where(WorkOrder.investigation_id == investigation.id)
            .order_by(WorkOrder.created_at)
        ).scalars()
    )
    departments = {
        row.id: row.name
        for row in ctx.session.execute(select(Department)).scalars()
    }
    evidence_rows = list(
        ctx.session.execute(
            select(Evidence).where(Evidence.investigation_id == investigation.id)
        ).scalars()
    )

    return ok(
        InvestigationDetail(
            investigation=investigation_out(investigation),
            incident=incident_out(incident) if incident else None,
            incident_evidence=[evidence_out(row) for row in incident_evidence],
            asset=asset_out(asset) if asset else None,
            nearby_assets=nearby,
            responsibility=responsibility,
            recommendations=[recommendation_out(row) for row in recommendations],
            work_orders=[
                work_order_out(row, department_name=departments.get(row.assigned_department_id))
                for row in work_orders
            ],
            evidence=[evidence_out(row) for row in evidence_rows],
            source_records=responsibility.source_references if responsibility else [],
            disclaimer=(
                registry_service.DISCLAIMER
            ),
        ),
        request,
    )


@router.patch("/investigations/{investigation_id}", response_model=Envelope[InvestigationOut])
def update_investigation(
    investigation_id: uuid.UUID,
    payload: InvestigationUpdate,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[InvestigationOut]:
    investigation = investigation_service.update_investigation(ctx, investigation_id, payload)
    return ok(investigation_out(investigation), request)


@router.post("/investigations/{investigation_id}/analyze", response_model=Envelope[InvestigationAnalysis])
def analyze_investigation(
    investigation_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[InvestigationAnalysis]:
    analysis = investigation_service.analyze_investigation(ctx, investigation_id)
    return ok(analysis, request)


@router.post("/investigations/{investigation_id}/assign", response_model=Envelope[InvestigationOut])
def assign_investigation(
    investigation_id: uuid.UUID,
    payload: InvestigationAssign,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[InvestigationOut]:
    investigation = investigation_service.assign_investigation(ctx, investigation_id, payload)
    return ok(investigation_out(investigation), request)


@router.get(
    "/investigations/{investigation_id}/recommendations",
    response_model=Envelope[list[RecommendationOut]],
)
def list_recommendations(
    investigation_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[list[RecommendationOut]]:
    ctx.require("investigation:read")
    rows = ctx.session.execute(
        select(Recommendation)
        .where(Recommendation.investigation_id == investigation_id)
        .order_by(Recommendation.created_at)
    ).scalars()
    return ok([recommendation_out(row) for row in rows], request)


@router.post(
    "/investigations/{investigation_id}/recommendations",
    response_model=Envelope[RecommendationOut],
    status_code=201,
)
def create_recommendation(
    investigation_id: uuid.UUID,
    payload: RecommendationCreate,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[RecommendationOut]:
    recommendation = investigation_service.create_recommendation(ctx, investigation_id, payload)
    return ok(recommendation_out(recommendation), request)


@router.patch("/recommendations/{recommendation_id}/review", response_model=Envelope[RecommendationOut])
def review_recommendation(
    recommendation_id: uuid.UUID,
    payload: RecommendationReview,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[RecommendationOut]:
    recommendation = investigation_service.review_recommendation(ctx, recommendation_id, payload)
    return ok(recommendation_out(recommendation), request)
