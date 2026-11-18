"""Upload validation.

The file extension and the browser-provided MIME type are not trusted on their
own: the container signature is checked as well. Full media inspection (duration,
resolution, decodability) happens in the asynchronous worker so a large file can
never block an API request.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from app.core.config import settings
from app.core.errors import PayloadTooLarge, UnsupportedMedia

SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    base = PurePosixPath(filename.replace("\\", "/")).name
    cleaned = SAFE_FILENAME.sub("_", base).strip("._") or "upload"
    return cleaned[:120]


def check_size(file_size_bytes: int) -> None:
    if file_size_bytes <= 0:
        raise UnsupportedMedia("The file is empty.")
    if file_size_bytes > settings.max_upload_bytes:
        raise PayloadTooLarge(
            f"The file exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit."
        )


def check_content_type(filename: str, content_type: str) -> str:
    extension = PurePosixPath(sanitize_filename(filename)).suffix.lower()
    normalized = (content_type or "").split(";")[0].strip().lower()
    if extension not in settings.supported_video_extensions:
        raise UnsupportedMedia(
            "Unsupported file extension. Allowed: "
            + ", ".join(sorted(settings.supported_video_extensions))
        )
    if normalized not in settings.supported_video_content_types:
        raise UnsupportedMedia(
            "Unsupported content type. Allowed: "
            + ", ".join(sorted(settings.supported_video_content_types))
        )
    return normalized


def sniff_container(head_bytes: bytes) -> str | None:
    """Return a container family from the first bytes of the file."""
    head = head_bytes[:32]
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in {b"qt  "}:
            return "quicktime"
        return "mp4"
    if head.startswith(b"\x1aE\xdf\xa3"):
        lowered = head_bytes[:64].lower()
        return "webm" if b"webm" in lowered else "matroska"
    return None


def verify_container(head_bytes: bytes) -> str:
    container = sniff_container(head_bytes)
    if container is None:
        raise UnsupportedMedia(
            "The uploaded file is not a recognised video container (mp4, mov, mkv or webm)."
        )
    return container


def media_limitations_note() -> list[str]:
    return [
        "CONTAINER_SIGNATURE_ONLY_IN_API",
        "DURATION_AND_RESOLUTION_VERIFIED_IN_WORKER",
    ]
