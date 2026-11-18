"""Private object storage adapters.

Bytes never travel through a public bucket: the API validates the upload session,
then issues a short-lived, single-purpose URL. Both backends implement the same
interface so the worker and API are storage-agnostic.
"""

from __future__ import annotations

import hashlib
import io
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import settings
from app.core.errors import DependencyUnavailable, NotFound
from app.core.security import create_signed_object_token

logger = logging.getLogger("roadguard.storage")


@dataclass(frozen=True)
class ObjectStat:
    exists: bool
    size_bytes: int


class StorageBackend(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str) -> None: ...

    def put_stream(self, key: str, stream: BinaryIO, content_type: str) -> int: ...

    def read_bytes(self, key: str) -> bytes: ...

    def open_stream(self, key: str) -> BinaryIO: ...

    def stat(self, key: str) -> ObjectStat: ...

    def delete(self, key: str) -> None: ...

    def upload_url(self, *, key: str, organization_id: uuid.UUID, content_type: str) -> str: ...

    def download_url(
        self,
        *,
        key: str,
        organization_id: uuid.UUID,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> str: ...


def build_storage_key(*parts: str) -> str:
    """Server-generated storage key. User-supplied paths are never used."""
    safe_parts = [part.strip("/").replace("..", "") for part in parts if part]
    return "/".join(safe_parts)


class LocalStorageBackend:
    """Development backend: a private directory plus signed API URLs."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        root = self.root.resolve()
        if root not in candidate.parents and candidate != root:
            raise NotFound("Object not found.")
        return candidate

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def put_stream(self, key: str, stream: BinaryIO, content_type: str) -> int:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with path.open("wb") as handle:
            while chunk := stream.read(1024 * 256):
                handle.write(chunk)
                written += len(chunk)
        return written

    def read_bytes(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise NotFound("Object not found.")
        return path.read_bytes()

    def open_stream(self, key: str) -> BinaryIO:
        path = self._path(key)
        if not path.is_file():
            raise NotFound("Object not found.")
        return path.open("rb")

    def stat(self, key: str) -> ObjectStat:
        path = self._path(key)
        if not path.is_file():
            return ObjectStat(exists=False, size_bytes=0)
        return ObjectStat(exists=True, size_bytes=path.stat().st_size)

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()

    def upload_url(self, *, key: str, organization_id: uuid.UUID, content_type: str) -> str:
        token = create_signed_object_token(
            organization_id=organization_id,
            storage_key=key,
            purpose="upload",
            ttl_seconds=settings.signed_url_ttl_seconds,
        )
        return f"/api/v1/storage/upload/{token}"

    def download_url(
        self,
        *,
        key: str,
        organization_id: uuid.UUID,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        token = create_signed_object_token(
            organization_id=organization_id,
            storage_key=key,
            purpose="download",
            ttl_seconds=settings.signed_url_ttl_seconds,
            content_type=content_type,
            filename=filename,
        )
        return f"/api/v1/storage/download/{token}"


class S3StorageBackend:
    """MinIO / S3-compatible private bucket."""

    def __init__(self) -> None:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise DependencyUnavailable("Object storage client is unavailable.") from exc

        client_kwargs = {
            "aws_access_key_id": settings.s3_access_key_id,
            "aws_secret_access_key": settings.s3_secret_access_key,
            "region_name": settings.s3_region,
            "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        }
        self._client = boto3.client(
            "s3", endpoint_url=settings.s3_endpoint_url, **client_kwargs
        )
        # Inside compose the bucket is reached at minio:9000, which a browser cannot
        # resolve. Presigned URLs are therefore signed against a separately
        # configured public endpoint when one is set.
        self._presign_client = (
            boto3.client("s3", endpoint_url=settings.s3_public_endpoint_url, **client_kwargs)
            if settings.s3_public_endpoint_url
            else self._client
        )
        self.bucket = settings.s3_bucket

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self._client.put_object(
                Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
            )
        except Exception as exc:
            logger.error("s3_put_failed key=%s error=%s", key, type(exc).__name__)
            raise DependencyUnavailable("Private object storage is unavailable.") from exc

    def put_stream(self, key: str, stream: BinaryIO, content_type: str) -> int:
        stream.seek(0, io.SEEK_END)
        size = stream.tell()
        stream.seek(0)
        try:
            self._client.upload_fileobj(
                stream, self.bucket, key, ExtraArgs={"ContentType": content_type}
            )
        except Exception as exc:
            logger.error("s3_upload_failed key=%s error=%s", key, type(exc).__name__)
            raise DependencyUnavailable("Private object storage is unavailable.") from exc
        return size

    def read_bytes(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            raise NotFound("Object not found.") from exc

    def open_stream(self, key: str) -> BinaryIO:
        return io.BytesIO(self.read_bytes(key))

    def stat(self, key: str) -> ObjectStat:
        try:
            response = self._client.head_object(Bucket=self.bucket, Key=key)
            return ObjectStat(exists=True, size_bytes=int(response["ContentLength"]))
        except Exception:
            return ObjectStat(exists=False, size_bytes=0)

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except Exception:
            logger.warning("s3_delete_failed key=%s", key)

    def upload_url(self, *, key: str, organization_id: uuid.UUID, content_type: str) -> str:
        try:
            return self._presign_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=settings.signed_url_ttl_seconds,
            )
        except Exception as exc:
            raise DependencyUnavailable("Private object storage is unavailable.") from exc

    def download_url(
        self,
        *,
        key: str,
        organization_id: uuid.UUID,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        params = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        if content_type:
            params["ResponseContentType"] = content_type
        try:
            return self._presign_client.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=settings.signed_url_ttl_seconds
            )
        except Exception as exc:
            raise DependencyUnavailable("Private object storage is unavailable.") from exc


_STORAGE: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _STORAGE
    if _STORAGE is None:
        if settings.storage_backend == "s3":
            _STORAGE = S3StorageBackend()
        else:
            _STORAGE = LocalStorageBackend(settings.local_storage_path)
    return _STORAGE


def reset_storage() -> None:
    """Used by tests to swap backends."""
    global _STORAGE
    _STORAGE = None


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 256), b""):
        digest.update(chunk)
    return digest.hexdigest()
