"""Authentication endpoints."""

from __future__ import annotations

from app.api.deps import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    CurrentContext,
    RequestContext,
)
from app.core.config import settings
from app.core.errors import RateLimited, ValidationError
from app.core.permissions import all_permissions_for_roles
from app.core.ratelimit import SlidingWindowLimiter
from app.core.security import generate_csrf_token
from app.schemas.common import Envelope, ok
from app.schemas.domain import (
    ChangePasswordRequest,
    LoginRequest,
    SessionResponse,
)
from app.schemas.serializers import current_user
from app.services import identity
from fastapi import APIRouter, Request, Response, status

router = APIRouter(prefix="/auth", tags=["auth"])

_login_limiter = SlidingWindowLimiter(settings.login_rate_limit_per_minute, 60.0)
REFRESH_PATH = f"{settings.api_prefix}/auth"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _set_session_cookies(response: Response, access_token: str, refresh_token: str) -> str:
    csrf_token = generate_csrf_token()
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=REFRESH_PATH,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return csrf_token


def _clear_session_cookies(response: Response) -> None:
    for name, path in ((ACCESS_COOKIE, "/"), (CSRF_COOKIE, "/"), (REFRESH_COOKIE, REFRESH_PATH)):
        response.delete_cookie(name, path=path)


@router.post("/login", response_model=Envelope[SessionResponse])
def login(payload: LoginRequest, request: Request, response: Response) -> Envelope[SessionResponse]:
    key = f"{_client_ip(request)}:{payload.email.strip().lower()}"
    if not _login_limiter.allow(key):
        raise RateLimited(
            "Too many sign-in attempts. Wait a minute and try again.",
            code="RATE_LIMITED",
            details=[{"field": "email", "reason": f"retry after {_login_limiter.retry_after_seconds(key)}s"}],
        )
    authenticated = identity.authenticate(
        email=payload.email,
        password=payload.password,
        organization_slug=payload.organization_slug,
        request_id=getattr(request.state, "request_id", None),
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )
    csrf_token = _set_session_cookies(
        response, authenticated.access_token, authenticated.refresh_token
    )
    permissions = sorted(all_permissions_for_roles([authenticated.user.role]))
    session = SessionResponse(
        user=current_user(
            authenticated.user, authenticated.organization, permissions, csrf_token=csrf_token
        ),
        expires_in=authenticated.expires_in,
    )
    return ok(session, request)


@router.post("/refresh", response_model=Envelope[SessionResponse])
def refresh(request: Request, response: Response) -> Envelope[SessionResponse]:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        _clear_session_cookies(response)
        from app.core.errors import AuthenticationError

        raise AuthenticationError("Your session has expired. Please sign in again.")
    authenticated = identity.rotate_session(
        refresh_token=raw,
        request_id=getattr(request.state, "request_id", None),
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )
    csrf_token = _set_session_cookies(
        response, authenticated.access_token, authenticated.refresh_token
    )
    permissions = sorted(all_permissions_for_roles([authenticated.user.role]))
    return ok(
        SessionResponse(
            user=current_user(
                authenticated.user, authenticated.organization, permissions, csrf_token=csrf_token
            ),
            expires_in=authenticated.expires_in,
        ),
        request,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> Response:
    identity.revoke_session(
        request.cookies.get(REFRESH_COOKIE),
        request_id=getattr(request.state, "request_id", None),
        actor_id=None,
    )
    _clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=Envelope[SessionResponse])
def me(request: Request, ctx: RequestContext = CurrentContext) -> Envelope[SessionResponse]:
    from app.db.session import tenant_session
    from app.models import Organization, User

    with tenant_session(ctx.organization_id) as session:
        user = session.get(User, ctx.user_id)
        organization = session.get(Organization, ctx.organization_id)
        if user is None or organization is None:
            from app.core.errors import AuthenticationError

            raise AuthenticationError("Your session is no longer valid.")
        payload = SessionResponse(
            user=current_user(user, organization, sorted(ctx.principal.permissions)),
            expires_in=settings.access_token_ttl_minutes * 60,
        )
    return ok(payload, request)


@router.get("/csrf", response_model=Envelope[dict])
def csrf(request: Request) -> Envelope[dict]:
    token = request.cookies.get(CSRF_COOKIE) or generate_csrf_token()
    return ok({"csrf_token": token}, request)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest, ctx: RequestContext = CurrentContext
) -> Response:
    if payload.current_password == payload.new_password:
        raise ValidationError(
            "The new password must differ from the current password.",
            code="PASSWORD_REUSED",
        )
    identity.change_password(
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        request_id=ctx.request_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
