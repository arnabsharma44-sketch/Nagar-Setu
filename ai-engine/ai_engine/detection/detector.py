"""Detection adapters.

Both adapters return the same ``Detection`` structure so event rules, tracking
and evidence rendering are detector-independent:

    Detection(frame_number, timestamp_offset_seconds, class_label, class_id,
              bbox=(x1, y1, x2, y2), score)

``score`` is a model-specific detection score, never a calibrated probability
that an event occurred.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Detection:
    frame_number: int
    timestamp_offset_seconds: float
    class_label: str
    class_id: int
    bbox: tuple[float, float, float, float]
    score: float
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def size(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return float(np.hypot(x2 - x1, y2 - y1))

    def as_dict(self) -> dict[str, Any]:
        return {
            "frame_number": self.frame_number,
            "timestamp_offset_seconds": self.timestamp_offset_seconds,
            "class_label": self.class_label,
            "class_id": self.class_id,
            "bbox": list(self.bbox),
            "score": self.score,
        }


class DetectorAdapter(abc.ABC):
    """Interface implemented by model adapters."""

    name: str
    version: str

    @abc.abstractmethod
    def warm_up(self) -> None:
        """Raise a clear error when the adapter cannot run."""

    @abc.abstractmethod
    def detect(self, frame: np.ndarray, *, frame_number: int, timestamp_offset: float) -> list[Detection]:
        ...

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version}
