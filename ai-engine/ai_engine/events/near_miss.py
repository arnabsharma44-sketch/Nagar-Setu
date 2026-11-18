"""E-01 near-miss candidate.

Ingredients actually implemented: image-plane proximity below a configurable
threshold relative to object scale, path convergence inside a time window, and an
optional evasive-motion proxy. This is a heuristic candidate, not proof that a
collision nearly occurred.
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

RULE_NAME = "near_miss_v1"
RULE_VERSION = "1.0.0"


def evaluate(tracks: list[Track], config: RuleConfig, *, excluded_pairs: set[tuple[int, int]] | None = None) -> list[CandidateEvent]:
    excluded = excluded_pairs or set()
    events: list[CandidateEvent] = []
    candidates = [track for track in tracks if track.frames >= config.near_miss_min_track_frames]

    for first, second in combinations(candidates, 2):
        pair_key = tuple(sorted((first.track_id, second.track_id)))
        if pair_key in excluded:
            continue
        pairs = aligned_points(first, second, config.near_miss_convergence_window_seconds)
        if len(pairs) < 3:
            continue

        ratios = [proximity_ratio(a, b) for a, b in pairs]
        min_ratio = min(ratios)
        min_index = ratios.index(min_ratio)
        if min_ratio > config.near_miss_proximity_ratio:
            continue

        # Convergence: the pair must close the gap, not merely start close.
        initial_ratio = ratios[0]
        converged = initial_ratio - min_ratio > 0.15 * max(initial_ratio, 1e-6)
        if not converged:
            continue

        before = [a for a, _ in pairs[:min_index]] or [pairs[0][0]]
        after = [a for a, _ in pairs[min_index:]] or [pairs[-1][0]]
        first_before = speed_proxy(before)
        first_after = speed_proxy(after)
        second_before = speed_proxy([b for _, b in pairs[:min_index]] or [pairs[0][1]])
        second_after = speed_proxy([b for _, b in pairs[min_index:]] or [pairs[-1][1]])
        evasive = any(
            before_speed > 1.0 and after_speed < 0.65 * before_speed
            for before_speed, after_speed in (
                (first_before, first_after),
                (second_before, second_after),
            )
        )

        reason_codes = ["TRAJECTORIES_CONVERGED", "LOW_IMAGE_PLANE_DISTANCE"]
        if evasive:
            reason_codes.append("EVASIVE_MOTION_PROXY")

        score = max(0.05, min(0.99, 1.0 - (min_ratio / max(config.near_miss_proximity_ratio, 1e-6))))
        events.append(
            CandidateEvent(
                event_type="near_miss_candidate",
                rule_name=RULE_NAME,
                rule_version=RULE_VERSION,
                start_offset_seconds=pairs[0][0].timestamp_offset_seconds,
                end_offset_seconds=pairs[-1][0].timestamp_offset_seconds,
                track_ids=[first.track_id, second.track_id],
                score=round(score, 3),
                features={
                    "minimum_image_plane_distance_ratio": round(min_ratio, 3),
                    "initial_image_plane_distance_ratio": round(initial_ratio, 3),
                    "trajectory_conflict": True,
                    "evasive_motion_proxy": evasive,
                    "tracks": [first.as_summary(), second.as_summary()],
                    "proximity_threshold": config.near_miss_proximity_ratio,
                },
                reason_codes=reason_codes,
                limitations=[
                    LIMITATION_UNCALIBRATED,
                    LIMITATION_IMAGE_PLANE,
                    LIMITATION_NOT_PROOF,
                    "HEURISTIC_THRESHOLDS_REQUIRE_CALIBRATION",
                ],
                severity="high" if min_ratio < 0.3 else "medium",
                best_frame_number=pairs[min_index][0].frame_number,
            )
        )
    return events
