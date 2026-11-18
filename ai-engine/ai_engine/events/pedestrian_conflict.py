"""E-06 pedestrian/cyclist-vehicle conflict candidate.

Requires a vulnerable road user track plus a vehicle track with converging
image-plane proximity. The person is never identified; only a job-local track id
is retained.
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
    is_vehicle,
    is_vulnerable,
    proximity_ratio,
)
from ai_engine.tracking.tracker import Track

RULE_NAME = "pedestrian_conflict_v1"
RULE_VERSION = "1.0.0"


def evaluate(tracks: list[Track], config: RuleConfig) -> list[CandidateEvent]:
    events: list[CandidateEvent] = []
    vulnerable = [track for track in tracks if is_vulnerable(track.class_label) and track.frames >= 3]
    vehicles = [track for track in tracks if is_vehicle(track.class_label) and track.frames >= 3]

    for person, vehicle in combinations([*vulnerable, *vehicles], 2):
        labels = {person.class_label, vehicle.class_label}
        # Pair one vulnerable road user with one vehicle, never two of a kind.
        if is_vulnerable(person.class_label) == is_vulnerable(vehicle.class_label):
            continue
        if not (labels & {"person", "bicycle"}):
            continue
        pairs = aligned_points(person, vehicle)
        if len(pairs) < 3:
            continue
        ratios = [proximity_ratio(a, b) for a, b in pairs]
        min_ratio = min(ratios)
        if min_ratio > config.pedestrian_conflict_ratio:
            continue
        if ratios[0] - min_ratio <= 0.1 * max(ratios[0], 1e-6):
            continue

        vulnerable_track = person if is_vulnerable(person.class_label) else vehicle
        vehicle_track = vehicle if is_vulnerable(person.class_label) else person
        events.append(
            CandidateEvent(
                event_type="pedestrian_vehicle_conflict_candidate",
                rule_name=RULE_NAME,
                rule_version=RULE_VERSION,
                start_offset_seconds=pairs[0][0].timestamp_offset_seconds,
                end_offset_seconds=pairs[-1][0].timestamp_offset_seconds,
                track_ids=[vulnerable_track.track_id, vehicle_track.track_id],
                score=round(max(0.05, min(0.99, 1.0 - min_ratio)), 3),
                features={
                    "vulnerable_user_class": vulnerable_track.class_label,
                    "vehicle_class": vehicle_track.class_label,
                    "minimum_image_plane_distance_ratio": round(min_ratio, 3),
                },
                reason_codes=["VULNERABLE_USER_VEHICLE_CONVERGENCE"],
                limitations=[
                    LIMITATION_UNCALIBRATED,
                    LIMITATION_IMAGE_PLANE,
                    LIMITATION_NOT_PROOF,
                    "PERSON_NOT_IDENTIFIED",
                ],
                severity="high" if min_ratio < 0.4 else "medium",
                best_frame_number=pairs[ratios.index(min_ratio)][0].frame_number,
            )
        )
    return events
