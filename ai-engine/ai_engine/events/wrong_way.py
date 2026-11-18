"""E-02 wrong-way candidate.

Requires a configured expected travel direction for the camera scene. Without that
configuration the rule reports itself as unavailable rather than guessing road
direction from an arbitrary clip.
"""

from __future__ import annotations

import math

from ai_engine.events.base import (
    LIMITATION_IMAGE_PLANE,
    LIMITATION_NOT_PROOF,
    LIMITATION_UNCALIBRATED,
    CandidateEvent,
    RuleConfig,
    RuleOutcome,
)
from ai_engine.tracking.tracker import Track

RULE_NAME = "wrong_way_v1"
RULE_VERSION = "1.0.0"


def evaluate(tracks: list[Track], config: RuleConfig, scene_config: dict | None) -> RuleOutcome:
    expected = (scene_config or {}).get("expected_direction_degrees")
    tolerance = float((scene_config or {}).get("direction_tolerance_degrees", 60.0))
    if expected is None:
        return RuleOutcome(
            name=RULE_NAME,
            version=RULE_VERSION,
            status="unavailable",
            note="No camera scene configuration defining an expected travel direction.",
        )

    events: list[CandidateEvent] = []
    for track in tracks:
        if track.frames < 5:
            continue
        (x0, y0) = track.points[0].center
        (x1, y1) = track.points[-1].center
        if math.dist((x0, y0), (x1, y1)) < 25:
            continue
        heading = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 360.0
        difference = abs(((heading - float(expected) + 180.0) % 360.0) - 180.0)
        if difference <= tolerance:
            continue
        events.append(
            CandidateEvent(
                event_type="wrong_way_candidate",
                rule_name=RULE_NAME,
                rule_version=RULE_VERSION,
                start_offset_seconds=track.points[0].timestamp_offset_seconds,
                end_offset_seconds=track.points[-1].timestamp_offset_seconds,
                track_ids=[track.track_id],
                score=round(min(0.95, difference / 180.0), 3),
                features={
                    "observed_heading_degrees": round(heading, 1),
                    "expected_heading_degrees": round(float(expected), 1),
                    "difference_degrees": round(difference, 1),
                    "tolerance_degrees": tolerance,
                },
                reason_codes=["HEADING_OPPOSES_CONFIGURED_DIRECTION"],
                limitations=[
                    LIMITATION_UNCALIBRATED,
                    LIMITATION_IMAGE_PLANE,
                    LIMITATION_NOT_PROOF,
                ],
                severity="medium",
                best_frame_number=track.points[len(track.points) // 2].frame_number,
            )
        )
    return RuleOutcome(name=RULE_NAME, version=RULE_VERSION, status="evaluated", events=events)
