"""Audit trail and user administration."""

from __future__ import annotations

import uuid

from app.api.deps import CurrentContext, RequestContext
from app.core.audit import record_audit
from app.core.errors import Conflict, NotFound, ValidationError
from app.core.permissions import ROLE_PERMISSIONS
from app.core.security import hash_password, normalize_email
from app.models import AuditLog, Department, User
from app.schemas.common import Envelope, ok, paginate
from app.schemas.domain import AuditLogOut, UserCreateRequest, UserOut, UserUpdateRequest
from app.schemas.serializers import audit_out, user_out
from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

router = APIRouter(tags=["audit"])


@router.get("/audit-logs", response_model=Envelope[list[AuditLogOut]])
def list_audit_logs(
    request: Request,
    action: str | None = Query(default=None, max_length=80),
    entity_type: str | None = Query(default=None, max_length=60),
    entity_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[AuditLogOut]]:
    ctx.require("audit:read")
    statement = select(AuditLog)
    count_statement = select(func.count()).select_from(AuditLog)
    if action:
        statement = statement.where(AuditLog.action == action)
        count_statement = count_statement.where(AuditLog.action == action)
    if entity_type:
        statement = statement.where(AuditLog.entity_type == entity_type)
        count_statement = count_statement.where(AuditLog.entity_type == entity_type)
    if entity_id:
        statement = statement.where(AuditLog.entity_id == entity_id)
        count_statement = count_statement.where(AuditLog.entity_id == entity_id)
    total = int(ctx.session.execute(count_statement).scalar_one())
    rows = ctx.session.execute(
        statement.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    ).scalars()
    return ok([audit_out(row) for row in rows], request, pagination=paginate(limit, offset, total))


@router.get("/users", response_model=Envelope[list[UserOut]])
def list_users(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[UserOut]]:
    ctx.require("user:manage")
    total = int(ctx.session.execute(select(func.count()).select_from(User)).scalar_one())
    rows = ctx.session.execute(
        select(User).order_by(User.full_name).limit(limit).offset(offset)
    ).scalars()
    return ok([user_out(row) for row in rows], request, pagination=paginate(limit, offset, total))


@router.post("/users", response_model=Envelope[UserOut], status_code=201)
def create_user(
    payload: UserCreateRequest, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[UserOut]:
    ctx.require("user:manage")
    if payload.role not in ROLE_PERMISSIONS:
        raise ValidationError(
            "Unknown role.",
            code="INVALID_ROLE",
            details=[{"field": "role", "reason": "must be one of " + ", ".join(sorted(ROLE_PERMISSIONS))}],
        )
    normalized = normalize_email(payload.email)
    existing = ctx.session.execute(
        select(User).where(User.normalized_email == normalized)
    ).scalar_one_or_none()
    if existing is not None:
        raise Conflict("A user with this email already exists.", code="DUPLICATE_EMAIL")
    if payload.department_id is not None:
        department = ctx.session.get(Department, payload.department_id)
        if department is None:
            raise NotFound("Department not found.")

    user = User(
        organization_id=ctx.organization_id,
        department_id=payload.department_id,
        full_name=payload.full_name.strip(),
        email=str(payload.email),
        normalized_email=normalized,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        is_demo=True,
    )
    ctx.session.add(user)
    ctx.session.flush()
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        request_id=ctx.request_id,
        summary=f"User {user.email} created with role {user.role}.",
    )
    return ok(user_out(user), request)


@router.patch("/users/{user_id}", response_model=Envelope[UserOut])
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[UserOut]:
    ctx.require("user:manage")
    user = ctx.session.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    if payload.role is not None:
        if payload.role not in ROLE_PERMISSIONS:
            raise ValidationError("Unknown role.", code="INVALID_ROLE")
        user.role = payload.role
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.department_id is not None:
        department = ctx.session.get(Department, payload.department_id)
        if department is None:
            raise NotFound("Department not found.")
        user.department_id = department.id
    if payload.is_active is not None:
        if user.id == ctx.user_id and payload.is_active is False:
            raise Conflict("You cannot deactivate your own account.", code="SELF_DEACTIVATION")
        user.is_active = payload.is_active
    ctx.session.flush()
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="user.updated",
        entity_type="user",
        entity_id=user.id,
        request_id=ctx.request_id,
        summary=f"User {user.email} updated.",
        metadata={"role": user.role, "is_active": user.is_active},
    )
    return ok(user_out(user), request)
