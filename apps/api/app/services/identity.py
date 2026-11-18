"""Identity service: authentication, session rotation and password change.

Login is the only place that reads across tenants, because an email address does
not yet identify an organization. That lookup uses the privileged role and
returns a single matched identity; every subsequent operation runs with the
organization context taken from the signed token.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.audit import record_audit
from app.core.errors import AuthenticationError, Conflict, NotFound
from app.core.permissions import all_permissions_for_roles
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    normalize_email,
    verify_password,
)
from app.db.session import privileged_session, tenant_session
from app.models import Organization, RefreshSession, User
from sqlalchemy import select
from sqlalchemy.orm import Session


class AuthenticatedUser:
    def __init__(self, user: User, organization: Organization, access_token: str, refresh_token: str, expires_in: int):
        self.user = user
        self.organization = organization
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in

    @property
    def permissions(self) -> list[str]:
        return sorted(all_permissions_for_roles([self.user.role]))


def _issue_tokens(
    session: Session, user: User, *, user_agent: str | None, ip_address: str | None
) -> tuple[str, str, int]:
    access_token, expires_in = create_access_token(
        user_id=user.id, organization_id=user.organization_id, role=user.role
    )
    session_id = uuid.uuid4()
    refresh_token, expires_at = create_refresh_token(
        user_id=user.id, organization_id=user.organization_id, session_id=session_id
    )
    record = RefreshSession(
        id=session_id,
        organization_id=user.organization_id,
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=expires_at,
        user_agent=(user_agent or "")[:255] or None,
        ip_address=(ip_address or "")[:64] or None,
    )
    session.add(record)
    return access_token, refresh_token, expires_in


def authenticate(
    *,
    email: str,
    password: str,
    organization_slug: str | None,
    request_id: str | None,
    user_agent: str | None,
    ip_address: str | None,
) -> AuthenticatedUser:
    normalized = normalize_email(email)
    with privileged_session() as lookup:
        statement = select(User).where(User.normalized_email == normalized)
        candidates = list(lookup.execute(statement).scalars().all())

    if organization_slug:
        with privileged_session() as lookup:
            org = lookup.execute(
                select(Organization).where(Organization.slug == organization_slug.strip().lower())
            ).scalar_one_or_none()
        candidates = [c for c in candidates if org and c.organization_id == org.id]

    if len(candidates) > 1:
        raise Conflict(
            "This email is registered with more than one organization. Provide organization_slug.",
            code="ORGANIZATION_REQUIRED",
        )
    if not candidates:
        # Same generic failure and comparable work as a bad password.
        verify_password(password, "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$aGFzaHZhbHVl")
        raise AuthenticationError("Email or password is incorrect.", code="INVALID_CREDENTIALS")

    user = candidates[0]
    if not verify_password(password, user.password_hash):
        raise AuthenticationError("Email or password is incorrect.", code="INVALID_CREDENTIALS")
    if not user.is_active:
        raise AuthenticationError("This account is disabled.", code="ACCOUNT_DISABLED")

    with tenant_session(user.organization_id) as session:
        db_user = session.get(User, user.id)
        if db_user is None or not db_user.is_active:
            raise AuthenticationError("This account is disabled.", code="ACCOUNT_DISABLED")
        db_user.last_login_at = datetime.now(UTC)
        access_token, refresh_token, expires_in = _issue_tokens(
            session, db_user, user_agent=user_agent, ip_address=ip_address
        )
        organization = session.get(Organization, db_user.organization_id)
        record_audit(
            session,
            organization_id=db_user.organization_id,
            actor_id=db_user.id,
            actor_label=db_user.email,
            action="auth.login",
            entity_type="user",
            entity_id=db_user.id,
            request_id=request_id,
            summary="User signed in.",
        )
        session.flush()
        session.expunge_all()

    return AuthenticatedUser(db_user, organization, access_token, refresh_token, expires_in)


def rotate_session(
    *, refresh_token: str, request_id: str | None, user_agent: str | None, ip_address: str | None
) -> AuthenticatedUser:
    payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    organization_id = uuid.UUID(str(payload["org"]))
    user_id = uuid.UUID(str(payload["sub"]))
    token_hash = hash_token(refresh_token)

    with tenant_session(organization_id) as session:
        record = session.execute(
            select(RefreshSession).where(RefreshSession.token_hash == token_hash)
        ).scalar_one_or_none()
        if record is None:
            raise AuthenticationError("Your session has expired. Please sign in again.")

        if record.revoked_at is not None:
            # Reuse of a rotated token: revoke every session for the account.
            sessions = session.execute(
                select(RefreshSession).where(
                    RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None)
                )
            ).scalars()
            now = datetime.now(UTC)
            for existing in sessions:
                existing.revoked_at = now
            record_audit(
                session,
                organization_id=organization_id,
                actor_id=user_id,
                action="auth.refresh_reuse_detected",
                entity_type="user",
                entity_id=user_id,
                request_id=request_id,
                summary="Refresh token reuse detected; all sessions revoked.",
            )
            raise AuthenticationError("Your session was revoked. Please sign in again.")

        if record.expires_at <= datetime.now(UTC):
            raise AuthenticationError("Your session has expired. Please sign in again.")

        user = session.get(User, user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Your session is no longer valid. Please sign in again.")

        access_token, new_refresh, expires_in = _issue_tokens(
            session, user, user_agent=user_agent, ip_address=ip_address
        )
        record.revoked_at = datetime.now(UTC)
        record.replaced_by_id = session.execute(
            select(RefreshSession.id)
            .where(RefreshSession.token_hash == hash_token(new_refresh))
            .limit(1)
        ).scalar_one_or_none()
        organization = session.get(Organization, user.organization_id)
        session.flush()
        session.expunge_all()

    return AuthenticatedUser(user, organization, access_token, new_refresh, expires_in)


def revoke_session(refresh_token: str | None, *, request_id: str | None, actor_id: uuid.UUID | None) -> None:
    if not refresh_token:
        return
    try:
        payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    except AuthenticationError:
        return
    organization_id = uuid.UUID(str(payload["org"]))
    token_hash = hash_token(refresh_token)
    with tenant_session(organization_id) as session:
        record = session.execute(
            select(RefreshSession).where(RefreshSession.token_hash == token_hash)
        ).scalar_one_or_none()
        if record and record.revoked_at is None:
            record.revoked_at = datetime.now(UTC)
            record_audit(
                session,
                organization_id=organization_id,
                actor_id=record.user_id,
                action="auth.logout",
                entity_type="user",
                entity_id=record.user_id,
                request_id=request_id,
                summary="User signed out.",
            )


def change_password(
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    current_password: str,
    new_password: str,
    request_id: str | None,
) -> None:
    with tenant_session(organization_id) as session:
        user = session.get(User, user_id)
        if user is None:
            raise NotFound("User not found.")
        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError("The current password is incorrect.", code="INVALID_CREDENTIALS")
        user.password_hash = hash_password(new_password)
        # Invalidate every other session after a password change.
        now = datetime.now(UTC)
        for record in session.execute(
            select(RefreshSession).where(
                RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None)
            )
        ).scalars():
            record.revoked_at = now
        record_audit(
            session,
            organization_id=organization_id,
            actor_id=user_id,
            actor_label=user.email,
            action="auth.password_changed",
            entity_type="user",
            entity_id=user_id,
            request_id=request_id,
            summary="Password changed; sessions revoked.",
        )
