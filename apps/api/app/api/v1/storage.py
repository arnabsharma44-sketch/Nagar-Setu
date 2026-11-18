"""Signed object endpoints for the local storage backend.

With ``STORAGE_BACKEND=s3`` the browser uploads directly to the private bucket and
these routes are unused. With ``local``, the short-lived token in the path carries
the organization, the storage key and a single purpose, so no session is required
and no client-supplied path is ever trusted.
"""

from __future__ import annotations

import os
import tempfile

from app.core.config import settings
from app.core.errors import PayloadTooLarge, ValidationError
from app.core.security import DOWNLOAD_TOKEN_TYPE, UPLOAD_TOKEN_TYPE, decode_token
from app.services.storage import get_storage
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/storage", tags=["storage"])

CHUNK_SIZE = 256 * 1024


@router.put("/upload/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def upload_object(token: str, request: Request) -> Response:
    payload = decode_token(token, expected_type=UPLOAD_TOKEN_TYPE)
    if payload.get("purpose") != "upload":
        raise ValidationError("This token cannot be used for uploads.", code="INVALID_TOKEN_PURPOSE")
    key = str(payload.get("key") or "")
    if not key or ".." in key:
        raise ValidationError("Invalid storage key.", code="INVALID_STORAGE_KEY")

    storage = get_storage()
    total = 0
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        temp_path = handle.name
        async for chunk in request.stream():
            total += len(chunk)
            if total > settings.max_upload_bytes:
                handle.close()
                os.unlink(temp_path)
                raise PayloadTooLarge("The uploaded file exceeds the configured limit.")
            handle.write(chunk)

    if total == 0:
        os.unlink(temp_path)
        raise ValidationError("The uploaded file is empty.")
    with open(temp_path, "rb") as reader:
        storage.put_stream(
            key, reader, request.headers.get("content-type", "application/octet-stream")
        )
    os.unlink(temp_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/download/{token}")
def download_object(token: str) -> StreamingResponse:
    payload = decode_token(token, expected_type=DOWNLOAD_TOKEN_TYPE)
    if payload.get("purpose") != "download":
        raise ValidationError("This token cannot be used for downloads.", code="INVALID_TOKEN_PURPOSE")
    key = str(payload.get("key") or "")
    if not key or ".." in key:
        raise ValidationError("Invalid storage key.", code="INVALID_STORAGE_KEY")

    storage = get_storage()
    stream = storage.open_stream(key)
    filename = str(payload.get("fn") or key.rsplit("/", 1)[-1])

    def chunks():  # noqa: ANN202
        try:
            while True:
                chunk = stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        finally:
            stream.close()

    return StreamingResponse(
        chunks(),
        media_type=str(payload.get("ct") or "application/octet-stream"),
        headers={
            "content-disposition": f'inline; filename="{filename}"',
            "cache-control": "private, no-store",
        },
    )


@router.get("/local-object-exists/{token}", response_model=dict)
def object_exists(token: str) -> dict:
    """Diagnostic helper for the local backend; requires a signed token."""
    payload = decode_token(token, expected_type=DOWNLOAD_TOKEN_TYPE)
    key = str(payload.get("key") or "")
    stat = get_storage().stat(key)
    return {"exists": stat.exists, "size_bytes": stat.size_bytes, "key_suffix": key[-12:]}
