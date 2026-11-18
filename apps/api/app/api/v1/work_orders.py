"""Work orders, completion evidence and independent verification."""

from __future__ import annotations

import uuid

from app.api.deps import CurrentContext, RequestContext
from app.core.errors import NotFound, ValidationError
from app.models import Department, WorkOrder
from app.schemas.common import Envelope, ok, paginate
from app.schemas.domain import (
    CompletionSubmit,
    EvidenceOut,
    VerificationSubmit,
    WorkOrderCreate,
    WorkOrderDetail,
    WorkOrderOut,
    WorkOrderUpdate,
)
from app.schemas.serializers import (
    evidence_out,
    status_history_out,
    verification_out,
    work_order_detail,
    work_order_out,
)
from app.services import videos as video_service
from app.services import work_orders as work_order_service
from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from sqlalchemy import func, select

router = APIRouter(prefix="/work-orders", tags=["work-orders"])


def _department_names(ctx: RequestContext) -> dict[uuid.UUID, str]:
    return {row.id: row.name for row in ctx.session.execute(select(Department)).scalars()}


@router.get("", response_model=Envelope[list[WorkOrderOut]])
def list_work_orders(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    investigation_id: uuid.UUID | None = Query(default=None),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[WorkOrderOut]]:
    ctx.require("work_order:read")
    statement = select(WorkOrder)
    count_statement = select(func.count()).select_from(WorkOrder)
    if investigation_id:
        statement = statement.where(WorkOrder.investigation_id == investigation_id)
        count_statement = count_statement.where(WorkOrder.investigation_id == investigation_id)
    total = int(ctx.session.execute(count_statement).scalar_one())
    rows = ctx.session.execute(
        statement.order_by(WorkOrder.created_at.desc()).limit(limit).offset(offset)
    ).scalars()
    departments = _department_names(ctx)
    return ok(
        [
            work_order_out(row, department_name=departments.get(row.assigned_department_id))
            for row in rows
        ],
        request,
        pagination=paginate(limit, offset, total),
    )


@router.post("", response_model=Envelope[WorkOrderOut], status_code=201)
def create_work_order(
    payload: WorkOrderCreate, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[WorkOrderOut]:
    order = work_order_service.create_work_order(ctx, payload)
    departments = _department_names(ctx)
    return ok(
        work_order_out(order, department_name=departments.get(order.assigned_department_id)), request
    )


@router.get("/{work_order_id}", response_model=Envelope[WorkOrderDetail])
def get_work_order(
    work_order_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[WorkOrderDetail]:
    ctx.require("work_order:read")
    order = work_order_service.get_work_order(ctx.session, work_order_id)
    payload = work_order_service.detail_payload(ctx, order)
    detail = work_order_detail(
        payload["order"],  # type: ignore[arg-type]
        department_name=payload["department_name"],  # type: ignore[arg-type]
        history=payload["history"],  # type: ignore[arg-type]
        verifications=payload["verifications"],  # type: ignore[arg-type]
        evidence=payload["evidence"],  # type: ignore[arg-type]
        allowed_transitions=payload["allowed_transitions"],  # type: ignore[arg-type]
        can_submit_completion=payload["can_submit_completion"],  # type: ignore[arg-type]
        can_verify=payload["can_verify"],  # type: ignore[arg-type]
    )
    return ok(detail, request)


@router.patch("/{work_order_id}", response_model=Envelope[WorkOrderOut])
def update_work_order(
    work_order_id: uuid.UUID,
    payload: WorkOrderUpdate,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[WorkOrderOut]:
    order = work_order_service.update_work_order(ctx, work_order_id, payload)
    departments = _department_names(ctx)
    return ok(
        work_order_out(order, department_name=departments.get(order.assigned_department_id)), request
    )


@router.post("/{work_order_id}/completion", response_model=Envelope[WorkOrderOut])
def submit_completion(
    work_order_id: uuid.UUID,
    payload: CompletionSubmit,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[WorkOrderOut]:
    order = work_order_service.submit_completion(ctx, work_order_id, payload)
    departments = _department_names(ctx)
    return ok(
        work_order_out(order, department_name=departments.get(order.assigned_department_id)), request
    )


@router.post("/{work_order_id}/evidence", response_model=Envelope[EvidenceOut], status_code=201)
async def upload_completion_evidence(
    work_order_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    label: str | None = Form(default=None),
    ctx: RequestContext = CurrentContext,
) -> Envelope[EvidenceOut]:
    ctx.require("work_order:complete")
    order = work_order_service.get_work_order(ctx.session, work_order_id)
    if order.status.value == "verified":
        raise ValidationError(
            "This work order is already verified; new completion evidence is not accepted.",
            code="WORK_ORDER_CLOSED",
        )
    content_type = (file.content_type or "application/octet-stream").split(";")[0].strip()
    allowed = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
    if content_type not in allowed:
        raise ValidationError(
            "Completion evidence must be an image (JPEG/PNG/WebP) or a PDF.",
            code="UNSUPPORTED_MEDIA_TYPE",
            details=[{"field": "file", "reason": content_type}],
        )
    data = await file.read()
    if not data:
        raise ValidationError("The evidence file is empty.", code="EMPTY_FILE")
    if len(data) > 15 * 1024 * 1024:
        raise ValidationError("Evidence files are limited to 15 MB.", code="FILE_TOO_LARGE")
    evidence = video_service.create_completion_evidence(
        ctx,
        work_order_id=order.id,
        filename=file.filename or "evidence",
        content_type=content_type,
        data=data,
        label=label,
    )
    return ok(evidence_out(evidence), request)


@router.post("/{work_order_id}/verifications", response_model=Envelope[WorkOrderDetail])
def submit_verification(
    work_order_id: uuid.UUID,
    payload: VerificationSubmit,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[WorkOrderDetail]:
    order = work_order_service.submit_verification(ctx, work_order_id, payload)
    detail_payload = work_order_service.detail_payload(ctx, order)
    detail = work_order_detail(
        detail_payload["order"],  # type: ignore[arg-type]
        department_name=detail_payload["department_name"],  # type: ignore[arg-type]
        history=detail_payload["history"],  # type: ignore[arg-type]
        verifications=detail_payload["verifications"],  # type: ignore[arg-type]
        evidence=detail_payload["evidence"],  # type: ignore[arg-type]
        allowed_transitions=detail_payload["allowed_transitions"],  # type: ignore[arg-type]
        can_submit_completion=detail_payload["can_submit_completion"],  # type: ignore[arg-type]
        can_verify=detail_payload["can_verify"],  # type: ignore[arg-type]
    )
    return ok(detail, request)


__all__ = ["router", "status_history_out", "verification_out", "NotFound"]
