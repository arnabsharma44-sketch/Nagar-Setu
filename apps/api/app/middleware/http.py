"""HTTP middleware: request correlation, security headers, CSRF and logging."""

from __future__ import annotations

import logging
import time
import uuid

from app.core.errors import error_body
from app.core.security import tokens_equal
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("roadguard.http")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Login establishes the CSRF cookie, and the signed-URL object endpoints are
# protected by a single-purpose signed token rather than a cookie session.
CSRF_EXEMPT_PREFIXES = (
    "/api/v1/auth/login",
    "/api/v1/storage/upload/",
    "/api/v1/health",
)


def _is_csrf_exempt(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in CSRF_EXEMPT_PREFIXES)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()

        if (
            request.method in UNSAFE_METHODS
            and request.cookies.get("roadguard_access")
            and not request.headers.get("authorization")
            and not _is_csrf_exempt(request.url.path)
        ):
            header_token = request.headers.get("x-csrf-token")
            cookie_token = request.cookies.get("roadguard_csrf")
            if not header_token or not cookie_token or not tokens_equal(header_token, cookie_token):
                return JSONResponse(
                    status_code=403,
                    content=error_body(
                        "CSRF_FAILED",
                        "The request could not be verified. Reload the page and retry.",
                        None,
                        request_id,
                    ),
                )

        try:
            response = await call_next(request)
        except Exception:  # pragma: no cover - re-raised for the app handler
            logger.exception("unhandled_error request_id=%s path=%s", request_id, request.url.path)
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["x-request-id"] = request_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "no-referrer"
        response.headers["permissions-policy"] = "geolocation=(), microphone=(), camera=()"
        if request.url.path.startswith("/api/"):
            response.headers["cache-control"] = response.headers.get(
                "cache-control", "no-store"
            )
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
