"""Investigation, analysis and recommendation workflow."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from app.api.deps import RequestContext
from app.core.audit import record_audit
from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.models import (
    Asset,
    Contract,
    ContractAsset,
    Department,
    Incident,
    Investigation,
    InvestigationStatus,
    Recommendation,
    RecommendationStatus,
    User,
)
from app.schemas.domain import (
    InvestigationAnalysis,
    InvestigationAssign,
    InvestigationCreate,
    InvestigationUpdate,
    RecommendationCreate,
    RecommendationReview,
)
from app.services import registry
from app.services.events import publish_event
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _next_case_number(session: Session, organization_id: uuid.UUID) -> str:
    year = datetime.now(UTC).year
    count = int(
        session.execute(
            select(func.count()).select_from(Investigation).where(
                Investigation.organization_id == organization_id
            )
        ).scalar_one()
    )
    return f"INV-{year}-{count + 1:04d}"


def create_investigation(ctx: RequestContext, payload: InvestigationCreate) -> Investigation:
    ctx.require("investigation:manage")
    incident: Incident | None = None
    if payload.incident_id is not None:
        incident = ctx.session.get(Incident, payload.incident_id)
        if incident is None:
            raise NotFound("Incident not found.")
    asset: Asset | None = None
    if payload.asset_id is not None:
        asset = ctx.session.get(Asset, payload.asset_id)
        if asset is None:
            raise NotFound("Asset not found.")
    if payload.assigned_department_id is not None:
        department = ctx.session.get(Department, payload.assigned_department_id)
        if department is None:
            raise NotFound("Department not found.")

    facts = [fact.strip() for fact in payload.observed_facts if fact.strip()]
    if incident is not None and not facts:
        facts.append(
            f"Linked incident {incident.id} of type {incident.incident_type.value} recorded at "
            f"{incident.event_time.isoformat()} with source kind {incident.source_kind.value}."
        )
        if incident.start_offset_seconds is not None and incident.end_offset_seconds is not None:
            facts.append(
                f"Source video offsets {incident.start_offset_seconds:.1f}s to "
                f"{incident.end_offset_seconds:.1f}s."
            )
        if incident.limitations:
            facts.append("Recorded limitations: " + ", ".join(str(x) for x in incident.limitations) + ".")

    responsibility = None
    if asset is not None:
        event_date: date | None = incident.event_time.date() if incident is not None else None
        responsibility = registry.build_responsibility(
            ctx.session, asset=asset, event_date=event_date
        )

    investigation = None
    for _attempt in range(3):
        case_number = _next_case_number(ctx.session, ctx.organization_id)
        candidate = Investigation(
            organization_id=ctx.organization_id,
            case_number=case_number,
            incident_id=incident.id if incident else None,
            asset_id=asset.id if asset else None,
            assigned_department_id=payload.assigned_department_id,
            title=payload.title.strip(),
            summary=payload.summary,
            observed_facts=facts,
            hypotheses=[],
            missing_information=[item for item in payload.missing_information if item.strip()],
            status=InvestigationStatus.OPEN,
            responsibility_status=responsibility.status if responsibility else None,
            opened_by=ctx.user_id,
            is_demo=settings.demo_mode,
        )
        try:
            with ctx.session.begin_nested():
                ctx.session.add(candidate)
                ctx.session.flush()
            investigation = candidate
            break
        except IntegrityError:
            continue
    if investigation is None:
        raise Conflict("Unable to allocate a case number. Please retry.", code="CASE_NUMBER_CONFLICT")

    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="investigation.created",
        entity_type="investigation",
        entity_id=investigation.id,
        request_id=ctx.request_id,
        summary=f"Investigation {investigation.case_number} opened.",
        metadata={"incident_id": str(incident.id) if incident else None},
    )
    publish_event(
        organization_id=ctx.organization_id,
        event_type="investigation.updated",
        resource_type="investigation",
        resource_id=investigation.id,
        data={"investigation_id": str(investigation.id), "status": investigation.status.value},
    )
    return investigation


def get_investigation(session: Session, investigation_id: uuid.UUID) -> Investigation:
    investigation = session.get(Investigation, investigation_id)
    if investigation is None:
        raise NotFound("Investigation not found.")
    return investigation


def update_investigation(
    ctx: RequestContext, investigation_id: uuid.UUID, payload: InvestigationUpdate
) -> Investigation:
    ctx.require("investigation:manage")
    investigation = get_investigation(ctx.session, investigation_id)
    changes: dict[str, object] = {}
    if payload.title is not None:
        investigation.title = payload.title.strip()
        changes["title"] = investigation.title
    if payload.summary is not None:
        investigation.summary = payload.summary
    if payload.status is not None:
        investigation.status = payload.status
        changes["status"] = payload.status.value
        if payload.status == InvestigationStatus.CLOSED:
            investigation.closed_by = ctx.user_id
            investigation.closed_at = datetime.now(UTC)
    if payload.observed_facts is not None:
        investigation.observed_facts = [fact.strip() for fact in payload.observed_facts if fact.strip()]
        changes["observed_facts_count"] = len(investigation.observed_facts)
    if payload.missing_information is not None:
        investigation.missing_information = [
            item.strip() for item in payload.missing_information if item.strip()
        ]
    ctx.session.flush()
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="investigation.updated",
        entity_type="investigation",
        entity_id=investigation.id,
        request_id=ctx.request_id,
        summary=f"Investigation {investigation.case_number} updated.",
        metadata=changes,
    )
    publish_event(
        organization_id=ctx.organization_id,
        event_type="investigation.updated",
        resource_type="investigation",
        resource_id=investigation.id,
        data={"investigation_id": str(investigation.id), "status": investigation.status.value},
    )
    return investigation


def assign_investigation(
    ctx: RequestContext, investigation_id: uuid.UUID, payload: InvestigationAssign
) -> Investigation:
    ctx.require("investigation:assign")
    investigation = get_investigation(ctx.session, investigation_id)
    if payload.department_id is not None:
        department = ctx.session.get(Department, payload.department_id)
        if department is None:
            raise NotFound("Department not found.")
        investigation.assigned_department_id = department.id
    if payload.assigned_to is not None:
        user = ctx.session.get(User, payload.assigned_to)
        if user is None:
            raise NotFound("User not found.")
        investigation.assigned_to = user.id
    if investigation.status == InvestigationStatus.OPEN:
        investigation.status = InvestigationStatus.UNDER_REVIEW
    ctx.session.flush()
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="investigation.assigned",
        entity_type="investigation",
        entity_id=investigation.id,
        request_id=ctx.request_id,
        summary=f"Investigation {investigation.case_number} assignment updated.",
        metadata={
            "department_id": str(payload.department_id) if payload.department_id else None,
            "assigned_to": str(payload.assigned_to) if payload.assigned_to else None,
            "note": payload.note,
        },
    )
    return investigation


def analyze_investigation(ctx: RequestContext, investigation_id: uuid.UUID) -> InvestigationAnalysis:
    ctx.require("investigation:manage")
    from ai_engine.investigation import llm as llm_module
    from ai_engine.investigation.root_cause import InvestigationInput, draft_analysis

    investigation = get_investigation(ctx.session, investigation_id)
    incident = (
        ctx.session.get(Incident, investigation.incident_id) if investigation.incident_id else None
    )
    asset = ctx.session.get(Asset, investigation.asset_id) if investigation.asset_id else None
    department = (
        ctx.session.get(Department, asset.department_id)
        if asset is not None and asset.department_id
        else None
    )

    contract_numbers: list[str] = []
    contract_expired = False
    missing_records: list[str] = []
    conflicts: list[str] = []
    source_references: list[str] = []
    if asset is not None:
        responsibility = registry.build_responsibility(
            ctx.session,
            asset=asset,
            event_date=incident.event_time.date() if incident else None,
        )
        contract_numbers = [contract.contract_number for contract in responsibility.contracts]
        contract_expired = bool(responsibility.contracts) and not any(
            contract.is_active_on_event_date for contract in responsibility.contracts
        )
        missing_records = responsibility.missing_records
        conflicts = responsibility.conflicts
        source_references = responsibility.source_references
        investigation.responsibility_status = responsibility.status

    payload = InvestigationInput(
        case_number=investigation.case_number,
        incident_type=incident.incident_type.value if incident else None,
        incident_source_kind=incident.source_kind.value if incident else None,
        incident_score=incident.model_score if incident else None,
        rule_name=incident.rule_name if incident else None,
        rule_version=incident.rule_version if incident else None,
        limitations=list(incident.limitations) if incident else [],
        asset_code=asset.asset_code if asset else None,
        asset_condition=asset.condition_status.value if asset else None,
        asset_id=str(asset.id) if asset else None,
        department_name=department.name if department else None,
        responsibility_status=investigation.responsibility_status.value
        if investigation.responsibility_status
        else None,
        contract_numbers=[str(number) for number in contract_numbers],
        contract_expired=contract_expired,
        missing_records=missing_records,
        conflicts=conflicts,
        source_references=source_references,
        review_status=incident.review_status.value if incident else None,
    )
    draft = draft_analysis(payload)
    analysis_source = "deterministic"
    model_name = draft["model_name"]

    provider = llm_module.build_provider(
        provider=settings.llm_provider,
        api_key=settings.openai_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
    )
    if provider is not None:
        try:
            import json

            raw = provider.complete_json(
                system=llm_module.SYSTEM_PROMPT,
                user=json.dumps(draft, default=str),
                schema_hint=llm_module.RESPONSE_SCHEMA_HINT,
            )
            sanitized = llm_module.sanitize_analysis(
                raw, model_name=f"{provider.name}:{settings.llm_model}"
            )
            sanitized["analysis_source"] = "llm"
            sanitized["generated_at"] = datetime.now(UTC).isoformat()
            draft = {**draft, **sanitized}
            analysis_source = "llm"
            model_name = sanitized["model_name"]
        except Exception as exc:  # pragma: no cover - provider outage path
            draft["limitations"].append(f"LLM_ASSISTANT_UNAVAILABLE:{type(exc).__name__}")

    investigation.hypotheses = draft["potential_root_causes"]
    investigation.missing_information = draft["missing_information"]
    investigation.analysis_source = analysis_source
    investigation.analysis_model = model_name
    investigation.analysis_generated_at = datetime.now(UTC)
    if not investigation.observed_facts:
        investigation.observed_facts = draft["observed_facts"]
    ctx.session.flush()

    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="investigation.analysis_generated",
        entity_type="investigation",
        entity_id=investigation.id,
        request_id=ctx.request_id,
        summary=f"Draft analysis generated ({analysis_source}).",
        metadata={"model": model_name, "hypotheses": len(draft["potential_root_causes"])},
    )

    return InvestigationAnalysis(
        investigation_id=investigation.id,
        analysis_source=analysis_source,
        model_name=model_name,
        generated_at=investigation.analysis_generated_at,
        observed_facts=draft["observed_facts"],
        potential_root_causes=draft["potential_root_causes"],
        missing_information=draft["missing_information"],
        potentially_relevant_authorities=draft["potentially_relevant_authorities"],
        recommended_actions=draft["recommended_actions"],
        limitations=draft["limitations"],
        human_verification_required=True,
    )


def create_recommendation(
    ctx: RequestContext, investigation_id: uuid.UUID, payload: RecommendationCreate
) -> Recommendation:
    ctx.require("investigation:manage")
    investigation = get_investigation(ctx.session, investigation_id)
    recommendation = Recommendation(
        organization_id=ctx.organization_id,
        investigation_id=investigation.id,
        recommendation_text=payload.recommendation_text.strip(),
        rationale=payload.rationale.strip(),
        priority=payload.priority,
        status=RecommendationStatus.DRAFT,
        limitations=list(payload.limitations),
        input_snapshot={
            "investigation_status": investigation.status.value,
            "responsibility_status": investigation.responsibility_status.value
            if investigation.responsibility_status
            else None,
            "hypotheses_count": len(investigation.hypotheses or []),
        },
        created_by=ctx.user_id,
        is_demo=settings.demo_mode,
    )
    ctx.session.add(recommendation)
    ctx.session.flush()
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="recommendation.drafted",
        entity_type="recommendation",
        entity_id=recommendation.id,
        request_id=ctx.request_id,
        summary=f"Draft recommendation added to {investigation.case_number}.",
    )
    return recommendation


def review_recommendation(
    ctx: RequestContext, recommendation_id: uuid.UUID, payload: RecommendationReview
) -> Recommendation:
    ctx.require("recommendation:review")
    recommendation = ctx.session.get(Recommendation, recommendation_id)
    if recommendation is None:
        raise NotFound("Recommendation not found.")
    if recommendation.status not in {RecommendationStatus.DRAFT, RecommendationStatus.SUPERSEDED}:
        raise Conflict(
            "Only a draft recommendation can be reviewed.", code="RECOMMENDATION_NOT_REVIEWABLE"
        )
    if recommendation.created_by == ctx.user_id and payload.decision == "approved":
        # Self-approval of AI drafts would defeat the human-approval control.
        raise Conflict(
            "The author of a draft cannot approve it. A different reviewer must decide.",
            code="SEPARATION_OF_DUTIES",
        )
    if not payload.notes:
        raise ValidationError(
            "A review note is required when approving or rejecting a recommendation.",
            code="REVIEW_NOTE_REQUIRED",
        )
    recommendation.status = (
        RecommendationStatus.APPROVED
        if payload.decision == "approved"
        else RecommendationStatus.REJECTED
    )
    recommendation.reviewed_by = ctx.user_id
    recommendation.reviewed_at = datetime.now(UTC)
    recommendation.review_notes = payload.notes
    ctx.session.flush()
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action=f"recommendation.{recommendation.status.value}",
        entity_type="recommendation",
        entity_id=recommendation.id,
        request_id=ctx.request_id,
        summary=f"Recommendation {recommendation.status.value}.",
        metadata={"notes": payload.notes},
    )
    return recommendation


def contract_context(session: Session, asset_id: uuid.UUID) -> list[Contract]:
    contract_ids = [
        row[0]
        for row in session.execute(
            select(ContractAsset.contract_id).where(ContractAsset.asset_id == asset_id)
        ).all()
    ]
    if not contract_ids:
        return []
    return list(session.execute(select(Contract).where(Contract.id.in_(contract_ids))).scalars())
