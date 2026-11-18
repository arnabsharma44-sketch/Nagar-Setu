"""Ultralytics YOLO adapter.

``ultralytics`` + ``torch`` are an optional extra because of their size. When the
package or weights are missing the adapter raises ``DetectorUnavailable`` so the
job fails visibly instead of emitting fabricated detections.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from ai_engine.detection.classes import CLASS_MAP
from ai_engine.detection.detector import Detection, DetectorAdapter


class DetectorUnavailable(RuntimeError):
    """Raised when the configured model cannot run in this environment."""


class YoloDetector(DetectorAdapter):
    name = "ultralytics-yolo"

    def __init__(self, *, weights: str, confidence: float = 0.35) -> None:
        self.weights = weights
        self.confidence = confidence
        self.version = "unloaded"
        self._model = None

    def warm_up(self) -> None:
        try:
            from ultralytics import YOLO  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - optional dependency
            raise DetectorUnavailable(
                "The YOLO detector backend requires the optional 'ultralytics' package. "
                "Install it (pip install ultralytics) or set DETECTOR_BACKEND=synthetic_scene "
                "for the generated demo clip."
            ) from exc
        weights_path = Path(self.weights)
        if not weights_path.exists() and weights_path.suffix and not weights_path.parent.exists():
            raise DetectorUnavailable(f"YOLO weights path is not available: {self.weights}")
        try:
            self._model = YOLO(str(self.weights))
        except Exception as exc:  # pragma: no cover - weights download failure
            raise DetectorUnavailable(f"Unable to load YOLO weights: {type(exc).__name__}") from exc
        version = getattr(self._model, "ckpt_path", None) or str(self.weights)
        self.version = f"yolo:{Path(str(version)).name}"

    def weights_sha256(self) -> str | None:
        try:
            from ultralytics import YOLO  # noqa: F401

            resolved = Path(str(getattr(self._model, "ckpt_path", self.weights)))
            if resolved.exists():
                return hashlib.sha256(resolved.read_bytes()).hexdigest()
        except Exception:  # pragma: no cover - best effort
            return None
        return None

    def detect(self, frame: np.ndarray, *, frame_number: int, timestamp_offset: float) -> list[Detection]:
        if self._model is None:  # pragma: no cover - defensive
            raise DetectorUnavailable("YOLO detector was not initialised.")
        results = self._model.predict(frame, conf=self.confidence, verbose=False)
        detections: list[Detection] = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                class_id = int(box.cls[0]) if box.cls is not None else -1
                spec = CLASS_MAP.get(class_id)
                if spec is None:
                    continue
                x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
                score = float(box.conf[0]) if box.conf is not None else 0.0
                detections.append(
                    Detection(
                        frame_number=frame_number,
                        timestamp_offset_seconds=timestamp_offset,
                        class_label=spec.label,
                        class_id=class_id,
                        bbox=(x1, y1, x2, y2),
                        score=round(score, 3),
                    )
                )
        return detections

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "kind": "yolo",
            "confidence_threshold": self.confidence,
            "weights": self.weights,
            "notes": "Model score is a detection confidence, not a calibrated event probability.",
        }


def build_detector(*, backend: str, weights: str, confidence: float) -> DetectorAdapter:
    if backend == "yolo":
        return YoloDetector(weights=weights, confidence=confidence)
    from ai_engine.detection.synthetic_scene import SyntheticSceneDetector

    return SyntheticSceneDetector()
