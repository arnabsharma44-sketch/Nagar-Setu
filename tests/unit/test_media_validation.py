"""Upload validation: size, extension/MIME agreement and container signature."""

from __future__ import annotations

import pytest
from app.core.config import settings
from app.core.errors import PayloadTooLarge, UnsupportedMedia
from app.services import media_validation


def test_filename_is_sanitised_against_path_traversal() -> None:
    assert media_validation.sanitize_filename("../../etc/passwd.mp4") == "passwd.mp4"
    assert media_validation.sanitize_filename("clip name?.mp4") == "clip_name_.mp4"
    assert media_validation.sanitize_filename("") == "upload"


def test_empty_file_is_rejected() -> None:
    with pytest.raises(UnsupportedMedia):
        media_validation.check_size(0)


def test_oversized_file_is_rejected() -> None:
    with pytest.raises(PayloadTooLarge):
        media_validation.check_size(settings.max_upload_bytes + 1)


def test_extension_must_be_a_video_extension() -> None:
    with pytest.raises(UnsupportedMedia):
        media_validation.check_content_type("payload.exe", "video/mp4")


def test_content_type_must_be_a_video_type() -> None:
    with pytest.raises(UnsupportedMedia):
        media_validation.check_content_type("clip.mp4", "text/html")


def test_valid_upload_returns_the_normalised_content_type() -> None:
    assert media_validation.check_content_type("clip.mp4", "Video/MP4; charset=binary") == "video/mp4"


def test_container_signature_detects_mp4_and_rejects_text() -> None:
    mp4_head = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 20
    assert media_validation.sniff_container(mp4_head) == "mp4"
    assert media_validation.sniff_container(b"%PDF-1.7 not a video at all") is None
    with pytest.raises(UnsupportedMedia):
        media_validation.verify_container(b"<html>not a video</html>")


def test_limitations_are_declared_for_the_api_layer() -> None:
    notes = media_validation.media_limitations_note()
    assert "CONTAINER_SIGNATURE_ONLY_IN_API" in notes
