"""Synthetic-scene detector.

Purpose
-------
The public demonstration must not use real surveillance footage, so demo clips are
generated locally by ``scripts/generate_demo_clip.py``: coloured markers on a
drawn road scene. This adapter *measures the pixels* of those clips (HSV colour
segmentation + contour extraction) and therefore exercises the same downstream
stages as a real model: frame sampling, tracking, event rules and evidence
rendering.

Honest limits
-------------
This is not a trained detector and it is not a substitute for one. It only works
on generated synthetic scenes whose markers use the documented palette, and the
score it reports is marker-mask purity, not a probability. Real footage uses the
YOLO adapter (``DETECTOR_BACKEND=yolo``).
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from ai_engine.detection.classes import LABEL_TO_ID
from ai_engine.detection.detector import Detection, DetectorAdapter

# BGR colours drawn by the demo generator. Keep in sync with
# scripts/generate_demo_clip.py.
MARKER_PALETTE: dict[str, tuple[int, int, int]] = {
    "car": (40, 40, 220),
    "truck": (40, 180, 40),
    "motorcycle": (220, 40, 220),
    "bicycle": (40, 200, 240),
    "person": (30, 160, 255),
    "bus": (220, 120, 40),
}

MIN_MARKER_AREA_PX = 120
COLOUR_TOLERANCE = 26


class SyntheticSceneDetector(DetectorAdapter):
    name = "synthetic-scene-colour-marker"
    version = "synthetic_scene_v1"

    def __init__(self, *, score_floor: float = 0.5) -> None:
        self.score_floor = score_floor

    def warm_up(self) -> None:
        # Nothing to load; fail loudly if OpenCV is unusable.
        if not hasattr(cv2, "inRange"):
            raise RuntimeError("OpenCV is not available in the worker environment.")

    def detect(self, frame: np.ndarray, *, frame_number: int, timestamp_offset: float) -> list[Detection]:
        detections: list[Detection] = []
        for label, colour in MARKER_PALETTE.items():
            lower = np.array([max(0, c - COLOUR_TOLERANCE) for c in colour], dtype=np.uint8)
            upper = np.array([min(255, c + COLOUR_TOLERANCE) for c in colour], dtype=np.uint8)
            mask = cv2.inRange(frame, lower, upper)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < MIN_MARKER_AREA_PX:
                    continue
                x, y, w, h = cv2.boundingRect(contour)
                if w < 6 or h < 6:
                    continue
                fill_ratio = float(area) / float(max(1, w * h))
                score = max(self.score_floor, min(0.99, 0.55 + 0.44 * fill_ratio))
                detections.append(
                    Detection(
                        frame_number=frame_number,
                        timestamp_offset_seconds=timestamp_offset,
                        class_label=label,
                        class_id=LABEL_TO_ID[label],
                        bbox=(float(x), float(y), float(x + w), float(y + h)),
                        score=round(score, 3),
                        extra={"marker_fill_ratio": round(fill_ratio, 3)},
                    )
                )
        return detections

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "kind": "synthetic_scene_colour_marker",
            "derivation": "subject",
            "palette": {label: list(colour) for label, colour in MARKER_PALETTE.items()},
            "notes": (
                "Detects colour markers in generated synthetic demo clips by HSV/BGR "
                "segmentation. Not a trained model; reports mask purity as a score."
            ),
        }
