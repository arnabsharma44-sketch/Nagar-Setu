"""Video ingestion validation tests.

Upload validation has two stages: the API checks extension/MIME/size and the
container signature on finalisation; the worker checks decodability. These tests
cover the API stage with the local storage backend and a stubbed stream.
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

from app.core.config import settings

CITY = "ops@demo.roadguard.ai"


def _camera_id(client) -> str:
    cameras = client.get("/api/v1/cameras").json()["data"]
    assert cameras, "need at least one seeded camera"
    return cameras[0]["id"]


class TestVideoPipeline:
    def test_upload_valid_mp4_returns_signed_url(self, client, login_as) -> None:
        login_as(CITY)
        response = client.post(
            "/api/v1/videos/upload-url",
            json={
                "filename": "test.mp4",
                "content_type": "video/mp4",
                "file_size_bytes": 1024 * 1024,
                "camera_id": _camera_id(client),
                "source_type": "upload",
            },
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["video_id"]
        assert data["upload_url"]
        assert data["max_bytes"] == settings.max_upload_bytes

    def test_upload_invalid_file_type_rejected(self, client, login_as) -> None:
        login_as(CITY)
        response = client.post(
            "/api/v1/videos/upload-url",
            json={
                "filename": "test.exe",
                "content_type": "application/octet-stream",
                "file_size_bytes": 1024,
            },
        )
        assert response.status_code == 415, response.text
        assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"

    def test_oversized_upload_rejected(self, client, login_as) -> None:
        login_as(CITY)
        response = client.post(
            "/api/v1/videos/upload-url",
            json={
                "filename": "huge.mp4",
                "content_type": "video/mp4",
                "file_size_bytes": settings.max_upload_bytes + 1,
            },
        )
        assert response.status_code == 413, response.text
        assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

    def test_non_video_bytes_fail_container_validation(self, client, login_as) -> None:
        """A file that merely claims to be an mp4 must not become a processing job."""
        login_as(CITY)
        store = MagicMock()
        store.upload_url.return_value = "/api/v1/storage/upload/stub-token"
        stat = MagicMock()
        stat.exists = True
        stat.size_bytes = 16
        store.stat.return_value = stat
        store.open_stream.return_value = io.BytesIO(b"this is not a video")

        with patch("app.services.videos.get_storage", return_value=store):
            signed = client.post(
                "/api/v1/videos/upload-url",
                json={
                    "filename": "fake.mp4",
                    "content_type": "video/mp4",
                    "file_size_bytes": 16,
                    "camera_id": _camera_id(client),
                },
            )
            assert signed.status_code == 201, signed.text
            video_id = signed.json()["data"]["video_id"]

            completed = client.post(f"/api/v1/videos/{video_id}/complete-upload")

        assert completed.status_code == 415, completed.text
        assert completed.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"

        video = client.get(f"/api/v1/videos/{video_id}").json()["data"]
        assert video["status"] == "pending_upload"
        jobs = client.get("/api/v1/jobs", params={"video_id": video_id}).json()["data"]
        assert jobs == [], "a rejected container must not enqueue an AI job"
