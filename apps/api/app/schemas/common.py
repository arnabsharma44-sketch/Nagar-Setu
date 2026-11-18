"""Shared request/response schema types."""

from __future__ import annotations

import math
from typing import Any, Generic, TypeVar

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Pagination(BaseModel):
    limit: int
    offset: int
    total: int
    has_more: bool


class Meta(BaseModel):
    request_id: str | None = None
    pagination: Pagination | None = None


class Envelope(BaseModel, Generic[T]):  # noqa: UP046 - Generic keeps parity with pydantic v2 typing
    data: T
    meta: Meta


class ErrorDetail(BaseModel):
    field: str | None = None
    reason: str


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorBody(BaseModel):
    error: ErrorPayload
    meta: Meta


def request_id(request: Request | None) -> str | None:
    if request is None:
        return None
    return getattr(request.state, "request_id", None)


def ok(
    data: Any,
    request: Request | None = None,
    *,
    pagination: Pagination | None = None,
) -> Envelope[Any]:
    return Envelope(data=data, meta=Meta(request_id=request_id(request), pagination=pagination))


def paginate(limit: int, offset: int, total: int) -> Pagination:
    return Pagination(limit=limit, offset=offset, total=total, has_more=offset + limit < total)


def page_count(total: int, limit: int) -> int:
    return math.ceil(total / limit) if limit else 0


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
