"""E-05 collision candidate.

Bounding-box overlap alone is explicitly insufficient: a candidate requires both
extreme proximity and an abrupt post-event motion change, and is still reported
as a candidate requiring human review.
"""

from __future__ import annotations

from itertools import combinations

from ai_engine.events.base import (
    LIMITATION_IMAGE_PLANE,
    LIMITATION_NOT_PROOF,
    LIMITATION_UNCALIBRATED,
    CandidateEvent,
    RuleConfig,
    aligned_points,
    proximity_ratio,
    speed_proxy,
)
from ai_engine.tracking.tracker import Track

RULE_NAME = "collision_v1"
RULE_VERSION = "1.0.0"


def evaluate(tracks: list[Track], config: RuleConfig) -> list[CandidateEvent]:
    events: list[CandidateEvent] = []
    candidates = [track for track in tracks if track.frames >= max(3, config.near_miss_min_track_frames - 2)]

    for first, second in combinations(candidates, 2):
        pairs = aligned_points(first, second)
        if len(pairs) < 3:
            continue
        ratios = [proximity_ratio(a, b) for a, b in pairs]
        min_ratio = min(ratios)
        if min_ratio > config.collision_proximity_ratio:
            continue
        min_index = ratios.index(min_ratio)

        before_points = [point for point in first.points if point.frame_number <= pairs[min_index][0].frame_number]
        after_points = [point for point in first.points if point.frame_number > pairs[min_index][0].frame_number]
        before = speed_proxy(before_points)
        after = speed_proxy(after_points)
        motion_change = before > 1.0 and (after < 0.5 * before or len(after_points) <= 1)
        if not motion_change:
            # Overlap without a motion change is not a collision candidate.
            continue

        events.append(
            CandidateEvent(
                event_type="collision_candidate",
                rule_name=RULE_NAME,
                rule_version=RULE_VERSION,
                start_offset_seconds=pairs[max(0, min_index - 2)][0].timestamp_offset_seconds,
                end_offset_seconds=pairs[-1][0].timestamp_offset_seconds,
                track_ids=[first.track_id, second.track_id],
                score=round(max(0.05, min(0.99, 1.0 - min_ratio)), 3),
                features={
                    "minimum_image_plane_distance_ratio": round(min_ratio, 3),
                    "motion_proxy_before": round(before, 2),
                    "motion_proxy_after": round(after, 2),
                    "motion_change_detected": True,
                    "bounding_box_overlap_alone": False,
                },
                reason_codes=[
                    "EXTREME_IMAGE_PLANE_PROXIMITY",
                    "ABRUPT_POST_EVENT_MOTION_CHANGE",
                ],
                limitations=[
                    LIMITATION_UNCALIBRATED,
                    LIMITATION_IMAGE_PLANE,
                    LIMITATION_NOT_PROOF,
                    "COLLISION_CLAIM_REQUIRES_HUMAN_REVIEW",
                ],
                severity="high",
                best_frame_number=pairs[min_index][0].frame_number,
            )
        )
    return events


def pairs_used(events: list[CandidateEvent]) -> set[tuple[int, int]]:
    return {tuple(sorted(event.track_ids)) for event in events if len(event.track_ids) == 2}
