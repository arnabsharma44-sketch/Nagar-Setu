"""Video pipeline integration tests."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4

from tests.conftest import DEMO_PASSWORD

CITY = "ops@demo.roadguard.ai"


class TestVideoPipeline:
    def test_upload_valid_mp4(self, client, login_as) -> None:
        login_as(CITY)
        cameras = client.get("/api/v1/cameras").json()["data"]
        assert cameras, "need at least one camera"
        camera_id = cameras[0]["id"]

        with patch("app.services.storage.get_storage") as mock_storage:
            mock_store = MagicMock()
            mock_store.upload_url.return_value = "https://minio/upload/url"
            mock_storage.return_value = mock_store

            response = client.post(
                "/api/v1/videos/upload-url",
                json={
                    "filename": "test.mp4",
                    "content_type": "video/mp4",
                    "file_size_bytes": 1024 * 1024,
                    "camera_id": camera_id,
                    "source_type": "upload",
                },
            )
        assert response.status_code == 201
        data = response.json()["data"]
        assert "video_id" in data
        assert "upload_url" in data

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
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"

    def test_oversized_upload_rejected(self, client, login_as) -> None:
        login_as(CITY)
        from app.core.config import settings
        response = client.post(
            "/api/v1/videos/upload-url",
            json={
                "filename": "huge.mp4",
                "content_type": "video/mp4",
                "file_size_bytes": settings.max_upload_bytes + 1,
            },
        )
def test_invalid_video_fails_processing(self, client, login_as) -> None:
        login_as(CITY)
        with patch("app.services.storage.get_storage") as mock_storage:
            mock_store = MagicMock()
            mock_store.stat.return_value.exists = True
            mock_store.stat.return_value.size_bytes = 1024
            mock_store.open_stream.return_value.__enter__.return_value.read.return_value = b"not a video"
            mock_storage.return_value = mock_store

            cameras = client.get("/api/v1/cameras").json()["data"]
            camera_id = cameras[0]["id"]

            response = client.post(
                "/api/v1/videos/upload-url",
                json={
                    "filename": "test.mp4",
                    "content_type": "video/mp4",
                    "file_size_bytes": 1024,
                    "camera_id": camera_id,
                },
            )
            video_id = response.json()["data"]["video_id"]

            client.post(f"/api/v1/videos/{video_id}/complete-upload")
            response = client.post(f"/api/v1/videos/{video_id}/process")
            assert response.status_code == 200

            # Wait for job to fail
            import time
            for _ in range(10):
                job_response = client.get(f"/api/v1/jobs?video_id={video_id}")
                jobs = job_response.json()["data"]
                if jobs and jobs[0]["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(1)

            assert jobs[0]["status"] == "failed"
            assert jobs[0]["error_code"] == "INVALID_MEDIA"
        assert response.status_code == 413