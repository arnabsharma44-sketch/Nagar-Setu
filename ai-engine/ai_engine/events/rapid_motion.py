"""E-03 rapid motion change candidate.

Without camera calibration a true deceleration cannot be measured, so this rule
uses an image-plane motion proxy and deliberately reports the weaker
``rapid_motion_change_candidate`` label rather than claiming sudden braking.
"""

from __future__ import annotations

from ai_engine.events.base import (
    LIMITATION_IMAGE_PLANE,
    LIMITATION_NOT_PROOF,
    LIMITATION_UNCALIBRATED,
    CandidateEvent,
    RuleConfig,
    speed_proxy,
)
from ai_engine.tracking.tracker import Track

RULE_NAME = "rapid_motion_change_v1"
RULE_VERSION = "1.0.0"


def evaluate(tracks: list[Track], config: RuleConfig) -> list[CandidateEvent]:
    events: list[CandidateEvent] = []
    for track in tracks:
        if track.frames < 6:
            continue
        midpoint = len(track.points) // 2
        before = speed_proxy(track.points[:midpoint])
        after = speed_proxy(track.points[midpoint:])
        if before < 3.0:
            continue
        if after > config.rapid_motion_change_ratio * before:
            continue
        drop_ratio = 1.0 - (after / before)
        events.append(
            CandidateEvent(
                event_type="rapid_motion_change_candidate",
                rule_name=RULE_NAME,
                rule_version=RULE_VERSION,
                start_offset_seconds=track.points[0].timestamp_offset_seconds,
                end_offset_seconds=track.points[-1].timestamp_offset_seconds,
                track_ids=[track.track_id],
                score=round(max(0.05, min(0.95, drop_ratio)), 3),
                features={
                    "class_label": track.class_label,
                    "motion_proxy_before": round(before, 2),
                    "motion_proxy_after": round(after, 2),
                    "motion_proxy_unit": "pixels_per_second_image_plane",
                },
                reason_codes=["IMAGE_PLANE_MOTION_REDUCTION"],
                limitations=[
                    LIMITATION_UNCALIBRATED,
                    LIMITATION_IMAGE_PLANE,
                    LIMITATION_NOT_PROOF,
                    "NOT_A_BRAKING_MEASUREMENT",
                ],
                severity="low",
                best_frame_number=track.points[midpoint].frame_number,
            )
        )
    return events
