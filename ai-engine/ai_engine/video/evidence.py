"""Evidence artefact generation.

Annotated frames and short clips are derived artefacts stored as separate private
objects. They support review; they are never presented as proof of causation.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable

import cv2
import numpy as np

ANNOTATION_COLOURS = {
    "car": (60, 60, 220),
    "truck": (60, 180, 60),
    "motorcycle": (220, 60, 220),
    "bicycle": (60, 200, 240),
    "person": (30, 160, 255),
    "bus": (220, 120, 40),
}


def annotate_frame(
    frame: np.ndarray,
    annotations: Iterable[tuple[int, str, tuple[float, float, float, float], float]],
    *,
    footer: str | None = None,
) -> np.ndarray:
    canvas = frame.copy()
    for track_id, label, bbox, score in annotations:
        x1, y1, x2, y2 = (int(round(value)) for value in bbox)
        colour = ANNOTATION_COLOURS.get(label, (200, 200, 200))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), colour, 2)
        text = f"#{track_id} {label} {score:.2f}"
        (text_width, text_height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(
            canvas,
            (x1, max(0, y1 - text_height - baseline - 4)),
            (x1 + text_width + 4, y1),
            colour,
            -1,
        )
        cv2.putText(
            canvas,
            text,
            (x1 + 2, max(text_height, y1 - baseline - 2)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    if footer:
        cv2.putText(
            canvas,
            footer,
            (10, canvas.shape[0] - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return canvas


def encode_png(frame: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", frame)
    if not ok:
        raise RuntimeError("Failed to encode evidence frame")
    return buffer.tobytes()


def build_event_clip(
    source_path: str,
    *,
    start_offset: float,
    end_offset: float,
    annotations_by_frame: dict[int, list[tuple[int, str, tuple[float, float, float, float], float]]],
    footer: str,
    max_seconds: float = 8.0,
) -> bytes | None:
    """Render a short annotated MP4 around the event window."""
    duration = max(0.5, min(max_seconds, end_offset - start_offset))
    capture = cv2.VideoCapture(source_path)
    if not capture.isOpened():
        return None
    frame_rate = float(capture.get(cv2.CAP_PROP_FPS) or 0.0) or 25.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fd, temp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    writer = cv2.VideoWriter(temp_path, cv2.VideoWriter_fourcc(*"mp4v"), frame_rate, (width, height))
    written = 0
    last_annotations: list[tuple[int, str, tuple[float, float, float, float], float]] = []
    try:
        frame_number = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            timestamp = frame_number / frame_rate
            if timestamp < start_offset:
                frame_number += 1
                continue
            if timestamp > start_offset + duration:
                break
            if frame_number in annotations_by_frame:
                last_annotations = annotations_by_frame[frame_number]
            writer.write(annotate_frame(frame, last_annotations, footer=footer))
            written += 1
            frame_number += 1
    finally:
        capture.release()
        writer.release()
    if written == 0:
        os.unlink(temp_path)
        return None
    with open(temp_path, "rb") as handle:
        data = handle.read()
    os.unlink(temp_path)
    return data
