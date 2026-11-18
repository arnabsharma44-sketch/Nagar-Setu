"""Event-rule primitives.

Every rule is versioned and returns candidate observations only. Measurements are
image-plane quantities; physical speed, metres and time-to-collision are never
derived from uncalibrated pixels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from ai_engine.tracking.tracker import Track, TrackPoint

LIMITATION_UNCALIBRATED = "CAMERA_NOT_METRIC_CALIBRATED"
LIMITATION_IMAGE_PLANE = "IMAGE_PLANE_MEASUREMENT_ONLY"
LIMITATION_NOT_PROOF = "CANDIDATE_OBSERVATION_NOT_CONFIRMED_EVENT"


@dataclass
class RuleConfig:
    near_miss_proximity_ratio: float = 0.55
    near_miss_convergence_window_seconds: float = 2.0
    near_miss_min_track_frames: int = 5
    collision_proximity_ratio: float = 0.25
    pedestrian_conflict_ratio: float = 0.7
    rapid_motion_change_ratio: float = 0.55

    def snapshot(self) -> dict[str, Any]:
        return {
            "near_miss_proximity_ratio": self.near_miss_proximity_ratio,
            "near_miss_convergence_window_seconds": self.near_miss_convergence_window_seconds,
            "near_miss_min_track_frames": self.near_miss_min_track_frames,
            "collision_proximity_ratio": self.collision_proximity_ratio,
            "pedestrian_conflict_ratio": self.pedestrian_conflict_ratio,
            "rapid_motion_change_ratio": self.rapid_motion_change_ratio,
        }


@dataclass
class CandidateEvent:
    event_type: str
    rule_name: str
    rule_version: str
    start_offset_seconds: float
    end_offset_seconds: float
    track_ids: list[int]
    score: float
    features: dict[str, Any] = field(default_factory=dict)
    reason_codes: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    severity: str = "medium"
    best_frame_number: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "rule_name": self.rule_name,
            "rule_version": self.rule_version,
            "start_offset_seconds": round(self.start_offset_seconds, 3),
            "end_offset_seconds": round(self.end_offset_seconds, 3),
            "track_ids": self.track_ids,
            "model_score": round(self.score, 3),
            "features": self.features,
            "reason_codes": self.reason_codes,
            "limitations": self.limitations,
            "severity": self.severity,
        }


@dataclass
class RuleOutcome:
    name: str
    version: str
    status: str  # "evaluated" | "unavailable"
    events: list[CandidateEvent] = field(default_factory=list)
    note: str | None = None


def aligned_points(
    first: Track, second: Track, window_seconds: float | None = None
) -> list[tuple[TrackPoint, TrackPoint]]:
    """Points of two tracks that coincide in time (frame-number aligned)."""
    second_by_frame = {point.frame_number: point for point in second.points}
    pairs = [
        (point, second_by_frame[point.frame_number])
        for point in first.points
        if point.frame_number in second_by_frame
    ]
    if window_seconds is not None and pairs:
        pairs = [
            pair
            for pair in pairs
            if pair[1].timestamp_offset_seconds - pair[0].timestamp_offset_seconds <= window_seconds
        ]
    return pairs


def proximity_ratio(first: TrackPoint, second: TrackPoint) -> float:
    """Centre distance normalised by the mean object size (image plane only)."""
    distance = math.dist(first.center, second.center)
    scale = max(1.0, (first.size + second.size) / 2.0)
    return distance / scale


def proximity_series(pairs: list[tuple[TrackPoint, TrackPoint]]) -> list[tuple[float, int, float]]:
    """``(timestamp, frame_number, ratio)`` for each aligned sample."""
    return [
        (a.timestamp_offset_seconds, a.frame_number, proximity_ratio(a, b)) for a, b in pairs
    ]


def speed_proxy(points: list[TrackPoint]) -> float:
    """Image-plane pixels per second (never a physical speed)."""
    if len(points) < 2:
        return 0.0
    total = 0.0
    for previous, current in zip(points, points[1:], strict=False):
        dt = current.timestamp_offset_seconds - previous.timestamp_offset_seconds
        if dt <= 0:
            continue
        total += math.dist(previous.center, current.center) / dt
    return total / max(1, len(points) - 1)


def is_vulnerable(label: str) -> bool:
    return label in {"person", "bicycle"}


def is_vehicle(label: str) -> bool:
    return label in {"car", "truck", "bus", "motorcycle"}
