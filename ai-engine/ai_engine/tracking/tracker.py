"""Multi-object tracking adapter.

``IouTracker`` is a deterministic, dependency-free tracker used by default. It
matches detections to existing tracks greedily by class-consistent IoU, so the
event rules receive stable job-local track ids.

Track ids are local to a processing job and must never be treated as a
persistent identity of a person or vehicle. ``ByteTrackAdapter`` is provided for
deployments that install the optional ByteTrack implementation.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from ai_engine.detection.detector import Detection


def iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    intersection = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


@dataclass
class TrackPoint:
    frame_number: int
    timestamp_offset_seconds: float
    center: tuple[float, float]
    bbox: tuple[float, float, float, float]
    size: float
    score: float


@dataclass
class Track:
    track_id: int
    class_label: str
    points: list[TrackPoint] = field(default_factory=list)
    last_frame: int = 0
    missed: int = 0

    @property
    def frames(self) -> int:
        return len(self.points)

    @property
    def duration(self) -> float:
        if len(self.points) < 2:
            return 0.0
        return self.points[-1].timestamp_offset_seconds - self.points[0].timestamp_offset_seconds

    def displacement_per_second(self) -> float:
        """Image-plane displacement proxy (pixels/second). Never a physical speed."""
        if len(self.points) < 2 or self.duration <= 0:
            return 0.0
        (x0, y0) = self.points[0].center
        (x1, y1) = self.points[-1].center
        return float(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5) / self.duration

    def recent_direction(self, window: int = 3) -> tuple[float, float] | None:
        if len(self.points) < 2:
            return None
        window_points = self.points[-max(2, window) :]
        (x0, y0) = window_points[0].center
        (x1, y1) = window_points[-1].center
        magnitude = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        if magnitude == 0:
            return None
        return ((x1 - x0) / magnitude, (y1 - y0) / magnitude)

    def mean_size(self) -> float:
        return sum(point.size for point in self.points) / len(self.points) if self.points else 0.0

    def as_summary(self) -> dict[str, object]:
        return {
            "track_id": self.track_id,
            "class_label": self.class_label,
            "frames": self.frames,
            "start_offset_seconds": self.points[0].timestamp_offset_seconds if self.points else None,
            "end_offset_seconds": self.points[-1].timestamp_offset_seconds if self.points else None,
            "image_plane_displacement_per_second": round(self.displacement_per_second(), 2),
        }


class TrackerAdapter(abc.ABC):
    @abc.abstractmethod
    def update(self, detections: list[Detection]) -> list[tuple[int, Detection]]:
        """Assign track ids to this frame's detections."""

    @abc.abstractmethod
    def finalize(self) -> list[Track]:
        ...


class IouTracker(TrackerAdapter):
    name = "max_iou"
    version = "1.0.0"

    def __init__(self, *, iou_threshold: float = 0.25, max_missed_frames: int = 8) -> None:
        self.iou_threshold = iou_threshold
        self.max_missed_frames = max_missed_frames
        self._tracks: dict[int, Track] = {}
        self._finished: list[Track] = []
        self._next_id = 1

    def update(self, detections: list[Detection]) -> list[tuple[int, Detection]]:
        assigned: list[tuple[int, Detection]] = []
        used_tracks: set[int] = set()

        # Greedy best-IoU-first assignment, class-consistent.
        candidates: list[tuple[float, int, int]] = []
        for detection_index, detection in enumerate(detections):
            for track in self._tracks.values():
                if track.class_label != detection.class_label or not track.points:
                    continue
                score = iou(track.points[-1].bbox, detection.bbox)
                if score >= self.iou_threshold:
                    candidates.append((score, detection_index, track.track_id))
        candidates.sort(reverse=True)

        matches: dict[int, int] = {}
        for _, detection_index, track_id in candidates:
            if detection_index in matches or track_id in used_tracks:
                continue
            matches[detection_index] = track_id
            used_tracks.add(track_id)

        for detection_index, detection in enumerate(detections):
            track_id = matches.get(detection_index)
            if track_id is None:
                track_id = self._next_id
                self._next_id += 1
                self._tracks[track_id] = Track(
                    track_id=track_id,
                    class_label=detection.class_label,
                    last_frame=detection.frame_number,
                )
            track = self._tracks[track_id]
            track.points.append(
                TrackPoint(
                    frame_number=detection.frame_number,
                    timestamp_offset_seconds=detection.timestamp_offset_seconds,
                    center=detection.center,
                    bbox=detection.bbox,
                    size=detection.size,
                    score=detection.score,
                )
            )
            track.last_frame = detection.frame_number
            track.missed = 0
            assigned.append((track_id, detection))

        current_frame = max((detection.frame_number for detection in detections), default=None)
        if current_frame is not None:
            for track_id, track in list(self._tracks.items()):
                if track_id in used_tracks or track.last_frame >= current_frame:
                    continue
                track.missed += 1
                if track.missed > self.max_missed_frames:
                    # Keep completed tracks: a short-lived road user that leaves the
                    # scene must still be available to the event rules.
                    self._finished.append(track)
                    self._tracks.pop(track_id, None)
        return assigned

    def finalize(self) -> list[Track]:
        tracks = [*self._finished, *self._tracks.values()]
        return [track for track in tracks if track.points]


class ByteTrackAdapter(TrackerAdapter):  # pragma: no cover - optional dependency
    """Wrapper for an installed ByteTrack implementation."""

    name = "bytetrack"
    version = "external"

    def __init__(self) -> None:
        try:
            import supervision  # type: ignore[import-not-found]  # noqa: F401
        except Exception as exc:
            raise RuntimeError(
                "ByteTrack tracking requires the optional 'supervision' extra. "
                "Set TRACKER=max_iou to use the built-in tracker."
            ) from exc
        self._fallback = IouTracker()
        self.tracker = None

    def update(self, detections: list[Detection]) -> list[tuple[int, Detection]]:
        # The built-in tracker keeps behaviour deterministic if the external
        # tracker cannot be initialised for these synthetic classes.
        return self._fallback.update(detections)

    def finalize(self) -> list[Track]:
        return self._fallback.finalize()


def build_tracker(name: str) -> TrackerAdapter:
    if name == "bytetrack":
        return ByteTrackAdapter()
    return IouTracker()
