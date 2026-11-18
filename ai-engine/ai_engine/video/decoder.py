"""Video probing, validation and frame sampling with OpenCV.

Original frame timestamps are preserved as offsets from the start of the source
file. Variable frame rate and missing metadata are handled by falling back to
sane defaults and recording a warning instead of failing silently.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

import cv2
import numpy as np


class VideoValidationError(RuntimeError):
    """Raised when a file cannot be decoded or exceeds configured limits."""


@dataclass
class VideoMetadata:
    width: int
    height: int
    frame_rate: float
    frame_count: int
    duration_seconds: float
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "width": self.width,
            "height": self.height,
            "frame_rate": round(self.frame_rate, 3),
            "frame_count": self.frame_count,
            "duration_seconds": round(self.duration_seconds, 3),
            "warnings": self.warnings,
        }


def probe(path: str) -> VideoMetadata:
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise VideoValidationError("The video could not be opened or decoded.")
    warnings: list[str] = []
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frame_rate = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_rate <= 0 or frame_rate != frame_rate:  # NaN guard
        frame_rate = 25.0
        warnings.append("FRAME_RATE_METADATA_MISSING")
    if frame_count <= 0:
        warnings.append("FRAME_COUNT_METADATA_MISSING")
    if width <= 0 or height <= 0:
        capture.release()
        raise VideoValidationError("The video has no readable frame dimensions.")
    duration = frame_count / frame_rate if frame_count > 0 else 0.0
    if duration <= 0:
        warnings.append("DURATION_UNKNOWN")
    capture.release()
    return VideoMetadata(
        width=width,
        height=height,
        frame_rate=frame_rate,
        frame_count=frame_count,
        duration_seconds=duration,
        warnings=warnings,
    )


def validate_limits(
    metadata: VideoMetadata,
    *,
    max_duration_seconds: int,
    max_width: int,
    max_height: int,
) -> None:
    if metadata.duration_seconds > max_duration_seconds:
        raise VideoValidationError(
            f"The clip is longer than the {max_duration_seconds}s processing limit."
        )
    if metadata.width > max_width or metadata.height > max_height:
        raise VideoValidationError(
            f"The clip resolution exceeds the {max_width}x{max_height} limit."
        )


def sample_step(frame_rate: float, sample_fps: float) -> int:
    if sample_fps <= 0:
        return 1
    return max(1, int(round(frame_rate / sample_fps)))


def iter_sampled_frames(
    path: str,
    *,
    sample_fps: float,
    start_offset: float = 0.0,
    end_offset: float | None = None,
) -> Iterator[tuple[int, float, np.ndarray]]:
    """Yield ``(frame_number, timestamp_offset_seconds, frame)`` at the sample rate."""
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise VideoValidationError("The video could not be opened or decoded.")
    frame_rate = float(capture.get(cv2.CAP_PROP_FPS) or 0.0) or 25.0
    step = sample_step(frame_rate, sample_fps)
    frame_number = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            timestamp = frame_number / frame_rate
            should_decode = frame_number % step == 0
            in_window = timestamp >= start_offset and (end_offset is None or timestamp <= end_offset)
            if should_decode and in_window:
                yield frame_number, timestamp, frame
            if end_offset is not None and timestamp > end_offset:
                break
            frame_number += 1
    finally:
        capture.release()


def read_frame_at(path: str, timestamp_offset: float) -> np.ndarray | None:
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        return None
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp_offset) * 1000.0)
        ok, frame = capture.read()
        return frame if ok else None
    finally:
        capture.release()
