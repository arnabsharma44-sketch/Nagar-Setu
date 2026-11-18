"""End-to-end analysis pipeline: decode → detect → track → rules → evidence inputs.

The pipeline is pure computation over a local file. Persistence, storage and job
state belong to the worker so this stage stays unit-testable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ai_engine.detection.detector import Detection, DetectorAdapter
from ai_engine.events.base import CandidateEvent, RuleConfig
from ai_engine.events.registry import evaluate_all, rule_manifest
from ai_engine.tracking.tracker import Track, build_tracker
from ai_engine.video.decoder import (
    VideoMetadata,
    iter_sampled_frames,
    probe,
    validate_limits,
)

logger = logging.getLogger("roadguard.pipeline")

ProgressCallback = Callable[[int, str], None]


@dataclass
class PipelineResult:
    metadata: VideoMetadata
    # (job-local track id, detection) pairs
    detections: list[tuple[int, Detection]]
    annotations_by_frame: dict[int, list[tuple[int, str, tuple[float, float, float, float], float]]]
    tracks: list[Track]
    events: list[CandidateEvent]
    rule_outcomes: list[dict[str, Any]]
    limitations: list[str] = field(default_factory=list)
    frames_processed: int = 0
    sample_fps: float = 5.0

    def summary(self) -> dict[str, Any]:
        return {
            "frames_processed": self.frames_processed,
            "tracks": len(self.tracks),
            "detections": len(self.detections),
            "events": len(self.events),
            "sample_fps": self.sample_fps,
            "media": self.metadata.as_dict(),
            "rule_manifest": rule_manifest(),
            "limitations": self.limitations,
        }


def analyze_video(
    path: str,
    *,
    detector: DetectorAdapter,
    sample_fps: float,
    rules: RuleConfig,
    tracker_name: str = "max_iou",
    scene_config: dict[str, Any] | None = None,
    max_duration_seconds: int = 600,
    max_width: int = 3840,
    max_height: int = 2160,
    progress: ProgressCallback | None = None,
    max_detections_persisted: int = 20000,
) -> PipelineResult:
    def report(value: int, stage: str) -> None:
        if progress:
            progress(max(0, min(100, value)), stage)

    report(5, "validating")
    metadata = probe(path)
    validate_limits(
        metadata,
        max_duration_seconds=max_duration_seconds,
        max_width=max_width,
        max_height=max_height,
    )
    detector.warm_up()

    tracker = build_tracker(tracker_name)
    detections: list[Detection] = []
    annotations_by_frame: dict[int, list[tuple[int, str, tuple[float, float, float, float], float]]] = {}
    frames_processed = 0
    total_frames = max(1, metadata.frame_count)
    report(12, "decoding")

    for frame_number, timestamp, frame in iter_sampled_frames(path, sample_fps=sample_fps):
        frame_detections = detector.detect(
            frame, frame_number=frame_number, timestamp_offset=timestamp
        )
        assigned = tracker.update(frame_detections)
        annotations = [
            (track_id, detection.class_label, detection.bbox, detection.score)
            for track_id, detection in assigned
        ]
        if annotations:
            annotations_by_frame[frame_number] = annotations
        if len(detections) < max_detections_persisted:
            detections.extend(assigned[: max_detections_persisted - len(detections)])
        frames_processed += 1
        if frames_processed % 10 == 0:
            percent = 12 + int(63 * min(1.0, frame_number / total_frames))
            report(percent, "tracking")

    tracks = tracker.finalize()
    report(80, "classifying")
    events, outcomes = evaluate_all(tracks, rules, scene_config)

    limitations = [
        "CANDIDATES_REQUIRE_HUMAN_REVIEW",
        "NO_PHYSICAL_SPEED_MEASUREMENT",
        "TRACK_IDS_ARE_JOB_LOCAL",
    ]
    if metadata.warnings:
        limitations.extend(metadata.warnings)
    if detector.describe().get("kind") == "synthetic_scene_colour_marker":
        limitations.append("DETECTOR_IS_SYNTHETIC_SCENE_COLOUR_MARKER_NOT_A_TRAINED_MODEL")

    report(88, "evidence")
    return PipelineResult(
        metadata=metadata,
        detections=detections,
        annotations_by_frame=annotations_by_frame,
        tracks=tracks,
        events=events,
        rule_outcomes=[
            {
                "name": outcome.name,
                "version": outcome.version,
                "status": outcome.status,
                "note": outcome.note,
                "event_count": len(outcome.events),
            }
            for outcome in outcomes
        ],
        limitations=limitations,
        frames_processed=frames_processed,
        sample_fps=sample_fps,
    )


def annotations_at(
    result: PipelineResult, frame_number: int
) -> list[tuple[int, str, tuple[float, float, float, float], float]]:
    if frame_number in result.annotations_by_frame:
        return result.annotations_by_frame[frame_number]
    if not result.annotations_by_frame:
        return []
    nearest = min(result.annotations_by_frame, key=lambda value: abs(value - frame_number))
    return result.annotations_by_frame[nearest]


def read_annotated_source(path: str, timestamp_offset: float, annotations) -> np.ndarray | None:
    from ai_engine.video.decoder import read_frame_at
    from ai_engine.video.evidence import annotate_frame

    frame = read_frame_at(path, timestamp_offset)
    if frame is None:
        return None
    return annotate_frame(
        frame,
        annotations,
        footer="ROADGUARD AI - candidate observation (not a confirmed accident)",
    )
