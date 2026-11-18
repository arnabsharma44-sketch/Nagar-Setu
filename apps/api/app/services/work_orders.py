"""Work-order lifecycle, completion and independent verification."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.deps import RequestContext
from app.core.audit import record_audit
from app.core.config import settings
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationError
from app.models import (
    WORK_ORDER_TRANSITIONS,
    Evidence,
    Investigation,
    Recommendation,
    RecommendationStatus,
    User,
    Verification,
    VerificationStatus,
    WorkOrder,
    WorkOrderStatus,
    WorkOrderStatusHistory,
)
from app.schemas.domain import (
    CompletionSubmit,
    VerificationSubmit,
    WorkOrderCreate,
    WorkOrderUpdate,
)
from app.services.events import publish_event
from sqlalchemy import func, select
from sqlalchemy.orm import Session

SEPARATION_OF_DUTIES = True


def _next_number(session: Session, organization_id: uuid.UUID) -> str:
    year = datetime.now(UTC).year
    count = int(
        session.execute(
            select(func.count())
            .select_from(WorkOrder)
            .where(WorkOrder.organization_id == organization_id)
        ).scalar_one()
    )
    return f"WO-{year}-{count + 1:04d}"


def _record_transition(
    ctx: RequestContext,
    order: WorkOrder,
    to_status: WorkOrderStatus,
    note: str | None,
) -> None:
    ctx.session.add(
        WorkOrderStatusHistory(
            organization_id=ctx.organization_id,
            work_order_id=order.id,
            from_status=order.status,
            to_status=to_status,
            changed_by=ctx.user_id,
            note=note,
        )
    )


def create_work_order(ctx: RequestContext, payload: WorkOrderCreate) -> WorkOrder:
    ctx.require("work_order:manage")
    investigation = ctx.session.get(Investigation, payload.investigation_id)
    if investigation is None:
        raise NotFound("Investigation not found.")
    from app.models import Department  # local import keeps module imports flat

    owning = ctx.session.get(Department, payload.assigned_department_id)
    if owning is None:
        raise NotFound("Department not found.")

    recommendation: Recommendation | None = None
    if payload.recommendation_id is not None:
        recommendation = ctx.session.get(Recommendation, payload.recommendation_id)
        if recommendation is None:
            raise NotFound("Recommendation not found.")
        if recommendation.investigation_id != investigation.id:
            raise ValidationError(
                "The recommendation belongs to a different investigation.",
                code="RECOMMENDATION_MISMATCH",
            )
        if recommendation.status != RecommendationStatus.APPROVED:
            raise Conflict(
                "Only an approved recommendation can become a work order.",
                code="RECOMMENDATION_NOT_APPROVED",
            )
    if payload.assigned_to is not None:
        assignee = ctx.session.get(User, payload.assigned_to)
        if assignee is None:
            raise NotFound("User not found.")

    order = WorkOrder(
        organization_id=ctx.organization_id,
        work_order_number=_next_number(ctx.session, ctx.organization_id),
        investigation_id=investigation.id,
        recommendation_id=recommendation.id if recommendation else None,
        assigned_department_id=owning.id,
        assigned_to=payload.assigned_to,
        title=payload.title.strip(),
        description=payload.description.strip(),
        status=WorkOrderStatus.ASSIGNED if payload.assigned_to else WorkOrderStatus.PENDING,
        priority=payload.priority,
        due_date=payload.due_date,
        created_by=ctx.user_id,
        is_demo=settings.demo_mode,
    )
    ctx.session.add(order)
    ctx.session.flush()
    ctx.session.add(
        WorkOrderStatusHistory(
            organization_id=ctx.organization_id,
            work_order_id=order.id,
            from_status=None,
            to_status=order.status,
            changed_by=ctx.user_id,
            note="Work order created.",
        )
    )
    investigation.assigned_department_id = investigation.assigned_department_id or owning.id
    ctx.session.flush()

    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="work_order.created",
        entity_type="work_order",
        entity_id=order.id,
        request_id=ctx.request_id,
        summary=f"Work order {order.work_order_number} created.",
        metadata={"department_id": str(owning.id), "investigation_id": str(investigation.id)},
    )
    publish_event(
        organization_id=ctx.organization_id,
        event_type="work_order.updated",
        resource_type="work_order",
        resource_id=order.id,
        data={"work_order_id": str(order.id), "status": order.status.value},
    )
    return order


def get_work_order(session: Session, work_order_id: uuid.UUID) -> WorkOrder:
    order = session.get(WorkOrder, work_order_id)
    if order is None:
        raise NotFound("Work order not found.")
    return order


def update_work_order(
    ctx: RequestContext, work_order_id: uuid.UUID, payload: WorkOrderUpdate
) -> WorkOrder:
    ctx.require("work_order:manage")
    order = get_work_order(ctx.session, work_order_id)
    if payload.status is not None and payload.status != order.status:
        allowed = WORK_ORDER_TRANSITIONS.get(order.status, set())
        if payload.status not in allowed:
            raise Conflict(
                f"Cannot move a work order from {order.status.value} to {payload.status.value}.",
                code="INVALID_TRANSITION",
                details=[{"field": "status", "reason": "transition not allowed"}],
            )
        if payload.status == WorkOrderStatus.VERIFIED:
            raise Conflict(
                "Use the verification endpoint to accept completion.",
                code="VERIFICATION_REQUIRED",
            )
        _record_transition(ctx, order, payload.status, payload.note)
        order.status = payload.status
        if payload.status == WorkOrderStatus.REOPENED:
            order.completed_at = None
            order.verified_at = None
            order.verified_by = None
    for field in ("title", "description", "priority", "due_date"):
        value = getattr(payload, field)
        if value is not None:
            setattr(order, field, value)
    if payload.assigned_to is not None:
        user = ctx.session.get(User, payload.assigned_to)
        if user is None:
            raise NotFound("User not found.")
        order.assigned_to = user.id
    ctx.session.flush()
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="work_order.updated",
        entity_type="work_order",
        entity_id=order.id,
        request_id=ctx.request_id,
        summary=f"Work order {order.work_order_number} updated.",
        metadata={"status": order.status.value},
    )
    publish_event(
        organization_id=ctx.organization_id,
        event_type="work_order.updated",
        resource_type="work_order",
        resource_id=order.id,
        data={"work_order_id": str(order.id), "status": order.status.value},
    )
    return order


def submit_completion(
    ctx: RequestContext, work_order_id: uuid.UUID, payload: CompletionSubmit
) -> WorkOrder:
    ctx.require("work_order:complete")
    order = get_work_order(ctx.session, work_order_id)
    if order.status not in {WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.ASSIGNED, WorkOrderStatus.REOPENED}:
        raise Conflict(
            f"A work order in state {order.status.value} cannot be submitted for verification.",
            code="INVALID_STATE",
        )
    evidence_rows: list[Evidence] = []
    for evidence_id in payload.evidence_ids:
        evidence = ctx.session.get(Evidence, evidence_id)
        if evidence is None or evidence.work_order_id != order.id:
            raise ValidationError(
                "Completion evidence must belong to this work order.",
                code="EVIDENCE_MISMATCH",
                details=[{"field": "evidence_ids", "reason": "not linked to this work order"}],
            )
        evidence_rows.append(evidence)
    if not evidence_rows:
        raise ValidationError(
            "Attach at least one evidence file before requesting verification.",
            code="EVIDENCE_REQUIRED",
        )

    _record_transition(
        ctx, order, WorkOrderStatus.COMPLETED_PENDING_VERIFICATION, payload.completion_notes[:500]
    )
    order.status = WorkOrderStatus.COMPLETED_PENDING_VERIFICATION
    order.completed_at = datetime.now(UTC)
    order.completed_by = ctx.user_id
    order.completion_notes = payload.completion_notes
    ctx.session.flush()
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="work_order.completion_submitted",
        entity_type="work_order",
        entity_id=order.id,
        request_id=ctx.request_id,
        summary=f"Completion submitted for {order.work_order_number}.",
        metadata={"evidence_ids": [str(row.id) for row in evidence_rows]},
    )
    publish_event(
        organization_id=ctx.organization_id,
        event_type="work_order.updated",
        resource_type="work_order",
        resource_id=order.id,
        data={"work_order_id": str(order.id), "status": order.status.value},
    )
    return order


def submit_verification(
    ctx: RequestContext, work_order_id: uuid.UUID, payload: VerificationSubmit
) -> WorkOrder:
    ctx.require("work_order:verify")
    order = get_work_order(ctx.session, work_order_id)
    if order.status != WorkOrderStatus.COMPLETED_PENDING_VERIFICATION:
        raise Conflict(
            "Only a work order pending verification can be verified.",
            code="INVALID_STATE",
        )
    if SEPARATION_OF_DUTIES and order.completed_by is not None and order.completed_by == ctx.user_id:
        raise PermissionDenied(
            "The person who submitted completion cannot verify it. A different reviewer is required.",
            code="SEPARATION_OF_DUTIES",
        )

    verification = Verification(
        organization_id=ctx.organization_id,
        work_order_id=order.id,
        verified_by=ctx.user_id,
        verification_status=payload.verification_status,
        notes=payload.notes,
        verified_at=datetime.now(UTC),
    )
    ctx.session.add(verification)

    if payload.verification_status == VerificationStatus.ACCEPTED:
        _record_transition(ctx, order, WorkOrderStatus.VERIFIED, payload.notes[:500])
        order.status = WorkOrderStatus.VERIFIED
        order.verified_at = datetime.now(UTC)
        order.verified_by = ctx.user_id
        investigation = ctx.session.get(Investigation, order.investigation_id)
        if investigation is not None:
            remaining = int(
                ctx.session.execute(
                    select(func.count())
                    .select_from(WorkOrder)
                    .where(
                        WorkOrder.investigation_id == investigation.id,
                        WorkOrder.id != order.id,
                        WorkOrder.status != WorkOrderStatus.VERIFIED,
                    )
                ).scalar_one()
            )
            if remaining == 0:
                from app.models import InvestigationStatus

                investigation.status = InvestigationStatus.CLOSED
                investigation.closed_at = datetime.now(UTC)
                investigation.closed_by = ctx.user_id
    elif payload.verification_status == VerificationStatus.REJECTED:
        _record_transition(ctx, order, WorkOrderStatus.REJECTED, payload.notes[:500])
        order.status = WorkOrderStatus.REJECTED
    else:
        _record_transition(ctx, order, WorkOrderStatus.REOPENED, payload.notes[:500])
        order.status = WorkOrderStatus.REOPENED
        order.completed_at = None
        order.completed_by = None
    ctx.session.flush()

    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action=f"work_order.verification_{payload.verification_status.value}",
        entity_type="work_order",
        entity_id=order.id,
        request_id=ctx.request_id,
        summary=f"Verification decision: {payload.verification_status.value}.",
        metadata={"notes": payload.notes},
    )
    publish_event(
        organization_id=ctx.organization_id,
        event_type="work_order.updated",
        resource_type="work_order",
        resource_id=order.id,
        data={"work_order_id": str(order.id), "status": order.status.value},
    )
    return order


def detail_payload(ctx: RequestContext, order: WorkOrder) -> dict[str, object]:
    from app.models import Department

    department = ctx.session.get(Department, order.assigned_department_id)
    history = list(
        ctx.session.execute(
            select(WorkOrderStatusHistory)
            .where(WorkOrderStatusHistory.work_order_id == order.id)
            .order_by(WorkOrderStatusHistory.created_at)
        ).scalars()
    )
    verifications = list(
        ctx.session.execute(
            select(Verification)
            .where(Verification.work_order_id == order.id)
            .order_by(Verification.created_at)
        ).scalars()
    )
    evidence = list(
        ctx.session.execute(
            select(Evidence).where(Evidence.work_order_id == order.id).order_by(Evidence.created_at)
        ).scalars()
    )
    can_submit = order.status in {
        WorkOrderStatus.IN_PROGRESS,
        WorkOrderStatus.ASSIGNED,
        WorkOrderStatus.REOPENED,
    } and ctx.principal.has("work_order:complete")
    can_verify = (
        order.status == WorkOrderStatus.COMPLETED_PENDING_VERIFICATION
        and ctx.principal.has("work_order:verify")
        and not (SEPARATION_OF_DUTIES and order.completed_by == ctx.user_id)
    )
    return {
        "order": order,
        "department_name": department.name if department else None,
        "history": history,
        "verifications": verifications,
        "evidence": evidence,
        "allowed_transitions": sorted(
            WORK_ORDER_TRANSITIONS.get(order.status, set()), key=lambda value: value.value
        ),
        "can_submit_completion": can_submit,
        "can_verify": can_verify,
    }
