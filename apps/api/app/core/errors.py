"""Consistent API error envelopes (see docs/05_API_SPEC.md §2)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """Application error carrying a stable machine code."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or []


class ValidationError(ApiError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"


class AuthenticationError(ApiError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "AUTHENTICATION_REQUIRED"


class PermissionDenied(ApiError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "PERMISSION_DENIED"


class NotFound(ApiError):
    """Also used for records that exist in another organization.

    A cross-tenant lookup must not disclose that the record exists, so callers
    receive 404 rather than 403 for foreign identifiers.
    """

    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class Conflict(ApiError):
    status_code = status.HTTP_409_CONFLICT
    code = "STATE_CONFLICT"


class PayloadTooLarge(ApiError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    code = "PAYLOAD_TOO_LARGE"


class UnsupportedMedia(ApiError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "UNSUPPORTED_MEDIA_TYPE"


class RateLimited(ApiError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMITED"


class DependencyUnavailable(ApiError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "DEPENDENCY_UNAVAILABLE"


def request_id_of(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_body(
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    return {
        "error": {"code": code, "message": message, "details": details or []},
        "meta": {"request_id": request_id},
    }


def success(data: Any, request_id: str | None = None, *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    payload_meta: dict[str, Any] = {"request_id": request_id}
    if meta:
        payload_meta.update(meta)
    return {"data": data, "meta": payload_meta}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details, request_id_of(request)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())[1:]),
                "reason": error.get("msg", "invalid"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_body(
                "VALIDATION_ERROR",
                "The request payload is invalid.",
                details,
                request_id_of(request),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "AUTHENTICATION_REQUIRED",
            403: "PERMISSION_DENIED",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "STATE_CONFLICT",
            413: "PAYLOAD_TOO_LARGE",
            415: "UNSUPPORTED_MEDIA_TYPE",
            429: "RATE_LIMITED",
        }.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message, None, request_id_of(request)),
        )
