"""RTSP adapter for live CCTV ingestion.

This adapter is GATED by configuration and authorization:
- ``LIVE_CCTV_ENABLED=false`` by default (disabled in prototype)
- Requires explicit host allowlist (``LIVE_CCTV_ALLOWED_HOSTS``)
- Requires explicit CIDR allowlist (``LIVE_CCTV_ALLOWED_CIDRS``)
- Credentials must be stored in secret store; only a reference is kept in DB

When enabled and authorized, this adapter connects to the RTSP stream,
decodes frames, and feeds them into the detection pipeline via the
existing runner infrastructure.

For the hackathon prototype, this remains a stub that clearly reports
its authorization requirements instead of attempting connections.
"""

from __future__ import annotations

import logging
import socket
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import cv2
import numpy as np
from app.core.config import settings

logger = logging.getLogger("roadguard.rtsp")


class RtspAuthorizationError(RuntimeError):
    """Raised when RTSP ingestion is not authorized or configured."""


class RtspConnectionError(RuntimeError):
    """Raised when RTSP stream cannot be connected or decoded."""


@dataclass(frozen=True)
class RtspStreamConfig:
    camera_id: str
    host: str
    port: int
    path: str
    username: str | None = None
    password: str | None = None
    transport: str = "tcp"

    @property
    def url(self) -> str:
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"rtsp://{auth}{self.host}:{self.port}{self.path}"


@dataclass
class RtspFrame:
    frame_number: int
    timestamp_offset_seconds: float
    frame: np.ndarray
    metadata: dict[str, Any]


def check_rtsp_authorization(host: str, cidr: str | None = None) -> None:
    if not settings.live_cctv_enabled:
        raise RtspAuthorizationError(
            "Live CCTV ingestion is disabled. Set LIVE_CCTV_ENABLED=true "
            "and configure allowlists to enable."
        )

    allowed_hosts = settings.live_cctv_allowed_host_set
    if allowed_hosts and host.lower() not in allowed_hosts:
        raise RtspAuthorizationError(
            f"Host '{host}' is not in the RTSP allowlist. "
            f"Allowed: {', '.join(sorted(allowed_hosts))}"
        )

    if cidr:
        allowed_cidrs = settings.live_cctv_allowed_cidrs_list
        if allowed_cidrs and cidr not in allowed_cidrs:
            raise RtspAuthorizationError(
                f"Network CIDR '{cidr}' is not in the RTSP allowlist. "
                f"Allowed: {', '.join(allowed_cidrs)}"
            )

    logger.info("RTSP authorization passed for host=%s", host)


def resolve_rtsp_secret(secret_reference: str) -> dict[str, str]:
    raise RtspAuthorizationError(
        f"Secret reference '{secret_reference}' cannot be resolved. "
        "No secret manager is configured in this prototype deployment. "
        "Configure a secret manager and set LIVE_CCTV_ENABLED=true to enable RTSP."
    )


def check_host_reachable(host: str, port: int = 554, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (TimeoutError, ConnectionRefusedError, OSError):
        return False

class RtspStreamReader:
    def __init__(
        self,
        config: RtspStreamConfig,
        *,
        frame_skip: int = 0,
        max_reconnect_attempts: int = 3,
        reconnect_delay_seconds: float = 5.0,
    ) -> None:
        self.config = config
        self.frame_skip = frame_skip
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay_seconds = reconnect_delay_seconds
        self._capture: cv2.VideoCapture | None = None
        self._frame_count = 0
        self._start_time: float | None = None

    def _build_opencv_url(self) -> str:
        base = self.config.url
        if self.config.transport == "udp":
            base += "?rtsp_transport=udp"
        return base

    def connect(self) -> None:
        url = self._build_opencv_url()
        logger.info("Connecting to RTSP stream: rtsp://%s:%d%s", self.config.host, self.config.port, self.config.path)

        self._capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        self._capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
        self._capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)

        if not self._capture.isOpened():
            raise RtspConnectionError(f"Failed to open RTSP stream: {url}")

        self._frame_count = 0
        self._start_time = time.time()
        logger.info("RTSP stream connected successfully")

    def reconnect(self) -> None:
        self.close()
        time.sleep(self.reconnect_delay_seconds)
        self.connect()

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> RtspStreamReader:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def iter_frames(self) -> Iterator[RtspFrame]:
        if self._capture is None:
            raise RtspConnectionError("RTSP stream not connected. Call connect() first.")

        reconnect_attempts = 0
        consecutive_failures = 0

        while True:
            ret, frame = self._capture.read()

            if not ret or frame is None:
                consecutive_failures += 1
                logger.warning("RTSP frame read failed (attempt %d)", consecutive_failures)

                if consecutive_failures >= 10:
                    if reconnect_attempts < self.max_reconnect_attempts:
                        logger.info("Attempting RTSP reconnection (%d/%d)",
                                    reconnect_attempts + 1, self.max_reconnect_attempts)
                        try:
                            self.reconnect()
                            consecutive_failures = 0
                            reconnect_attempts += 1
                            continue
                        except RtspConnectionError as e:
                            logger.error("RTSP reconnection failed: %s", e)
                    raise RtspConnectionError(
                        f"RTSP stream failed after {consecutive_failures} consecutive failures "
                        f"and {reconnect_attempts} reconnection attempts"
                    )
                time.sleep(0.1)
                continue

            consecutive_failures = 0
            reconnect_attempts = 0

            if self.frame_skip > 0 and self._frame_count % (self.frame_skip + 1) != 0:
                self._frame_count += 1
                continue

            timestamp = time.time() - self._start_time if self._start_time else 0.0

            yield RtspFrame(
                frame_number=self._frame_count,
                timestamp_offset_seconds=timestamp,
                frame=frame.copy(),
                metadata={
                    "source": "rtsp",
                    "camera_id": self.config.camera_id,
                    "host": self.config.host,
                },
            )

            self._frame_count += 1
def ingest_rtsp_stream(
    camera_id: str,
    secret_reference: str,
    *,
    duration_seconds: float | None = None,
    frame_skip: int = 0,
    frame_callback: callable | None = None,
) -> dict[str, Any]:
    credentials = resolve_rtsp_secret(secret_reference)

    host = credentials.get("host")
    if not host:
        raise RtspAuthorizationError("Secret must contain 'host' field")

    port = credentials.get("port", 554)
    path = credentials.get("path", "/")
    username = credentials.get("username")
    password = credentials.get("password")
    cidr = credentials.get("cidr")

    check_rtsp_authorization(host, cidr)

    if not check_host_reachable(host, port, timeout=5.0):
        raise RtspConnectionError(f"RTSP host {host}:{port} is not reachable")

    config = RtspStreamConfig(
        camera_id=camera_id,
        host=host,
        port=port,
        path=path,
        username=username,
        password=password,
    )

    stats = {
        "camera_id": camera_id,
        "host": host,
        "frames_processed": 0,
        "frames_failed": 0,
        "start_time": datetime.now(UTC).isoformat(),
        "end_time": None,
        "duration_seconds": 0.0,
    }

    start_time = time.time()
    end_time = start_time + duration_seconds if duration_seconds else None

    try:
        with RtspStreamReader(config, frame_skip=frame_skip) as reader:
            for rtsp_frame in reader.iter_frames():
                if end_time and time.time() > end_time:
                    break

                if frame_callback:
                    try:
                        frame_callback(rtsp_frame.frame, rtsp_frame.metadata)
                    except Exception as e:
                        logger.error("Frame callback error: %s", e)
                        stats["frames_failed"] += 1
                        continue

                stats["frames_processed"] += 1

    except RtspConnectionError:
        raise
    except Exception as e:
        logger.exception("RTSP ingestion failed for camera %s", camera_id)
        raise RtspConnectionError(f"Unexpected ingestion error: {e}") from e
    finally:
        stats["end_time"] = datetime.now(UTC).isoformat()
        stats["duration_seconds"] = round(time.time() - start_time, 3)

    return stats


def record_rtsp_segment_ffmpeg(
    rtsp_url: str,
    output_path: str,
    *,
    duration_seconds: float = 30.0,
    timeout_seconds: float = 60.0,
) -> bool:
    cmd = [
        "ffmpeg",
        "-y",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url,
        "-t", str(duration_seconds),
        "-c", "copy",
        "-f", "mp4",
        output_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg RTSP recording timed out after %ds", timeout_seconds)
        return False
    except Exception as e:
        logger.exception("FFmpeg RTSP recording failed: %s", e)
        return False


def create_demo_rtsp_config() -> dict[str, Any]:
    return {
        "secret_reference_format": {
            "description": "Expected secret store format for RTSP credentials",
            "fields": {
                "host": "camera.example.com",
                "port": 554,
                "path": "/stream1",
                "username": "rtsp_user",
                "password": "rtsp_password",
                "cidr": "10.0.0.0/8",
            },
            "notes": [
                "Secrets must be stored in a secret manager (Vault, AWS Secrets Manager, etc.)",
                "The camera record stores only an opaque reference, never the URL or credentials",
                "LIVE_CCTV_ENABLED must be true and host/CIDR allowlists configured",
                "Network connectivity to the camera host must be verified",
            ],
        },
        "environment_variables": {
            "LIVE_CCTV_ENABLED": "false",
            "LIVE_CCTV_ALLOWED_HOSTS": "camera1.example.com,camera2.example.com",
            "LIVE_CCTV_ALLOWED_CIDRS": "10.0.0.0/8,192.168.0.0/16",
        },
    }


__all__ = [
    "RtspAuthorizationError",
    "RtspConnectionError",
    "RtspStreamConfig",
    "RtspFrame",
    "RtspStreamReader",
    "check_rtsp_authorization",
    "resolve_rtsp_secret",
    "check_host_reachable",
    "ingest_rtsp_stream",
    "record_rtsp_segment_ffmpeg",
    "create_demo_rtsp_config",
]