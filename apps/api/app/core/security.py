"""Password hashing, JWT issuing/verification and CSRF helpers."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from app.core.config import settings
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
REALTIME_TOKEN_TYPE = "realtime"
UPLOAD_TOKEN_TYPE = "object_upload"
DOWNLOAD_TOKEN_TYPE = "object_download"

MAX_SIGNED_URL_TTL_SECONDS = 3600


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_token(raw_token: str) -> str:
    """Refresh tokens are persisted only as SHA-256 hashes."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _encode(payload: dict[str, Any], ttl: timedelta) -> str:
    now = datetime.now(UTC)
    body = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": str(uuid.uuid4()),
        "iss": "roadguard-ai",
    }
    return jwt.encode(body, settings.secret_key, algorithm="HS256")


def create_access_token(*, user_id: uuid.UUID, organization_id: uuid.UUID, role: str) -> tuple[str, int]:
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    token = _encode(
        {
            "type": ACCESS_TOKEN_TYPE,
            "sub": str(user_id),
            "org": str(organization_id),
            "role": role,
        },
        ttl,
    )
    return token, int(ttl.total_seconds())


def create_refresh_token(*, user_id: uuid.UUID, organization_id: uuid.UUID, session_id: uuid.UUID) -> tuple[str, datetime]:
    ttl = timedelta(days=settings.refresh_token_ttl_days)
    token = _encode(
        {
            "type": REFRESH_TOKEN_TYPE,
            "sub": str(user_id),
            "org": str(organization_id),
            "sid": str(session_id),
        },
        ttl,
    )
    return token, datetime.now(UTC) + ttl


def create_realtime_ticket(*, user_id: uuid.UUID, organization_id: uuid.UUID) -> str:
    """Short-lived single-use ticket used to open the WebSocket.

    The browser never sends an organization id: the socket gateway derives the
    tenant from this signed ticket.
    """
    return _encode(
        {"type": REALTIME_TOKEN_TYPE, "sub": str(user_id), "org": str(organization_id)},
        timedelta(seconds=60),
    )


def create_signed_object_token(
    *,
    organization_id: uuid.UUID,
    storage_key: str,
    purpose: Literal["upload", "download"],
    ttl_seconds: int,
    content_type: str | None = None,
    filename: str | None = None,
) -> str:
    ttl = min(ttl_seconds, MAX_SIGNED_URL_TTL_SECONDS)
    return _encode(
        {
            "type": "object_upload" if purpose == "upload" else "object_download",
            "org": str(organization_id),
            "key": storage_key,
            "purpose": purpose,
            "ct": content_type,
            "fn": filename,
        },
        timedelta(seconds=ttl),
    )


def decode_token(raw_token: str, *, expected_type: str) -> dict[str, Any]:
    from app.core.errors import AuthenticationError

    try:
        payload = jwt.decode(raw_token, settings.secret_key, algorithms=["HS256"], issuer="roadguard-ai")
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Your session has expired. Please sign in again.", code="TOKEN_EXPIRED") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("The supplied credential is not valid.") from exc
    if payload.get("type") != expected_type:
        raise AuthenticationError("The supplied credential is not valid for this operation.")
    return payload


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def tokens_equal(left: str, right: str) -> bool:
    return secrets.compare_digest(left, right)


def constant_time_dummy_verify() -> None:
    """Burn comparable CPU time for unknown accounts (avoids user enumeration)."""
    verify_password("not-a-real-password", _hasher.hash("not-a-real-password"))
