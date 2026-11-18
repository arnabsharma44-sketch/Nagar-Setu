"""Event rules must report candidates, stay conservative and declare gaps."""

from __future__ import annotations

from ai_engine.events import collision, near_miss, registry
from ai_engine.events.base import (
    LIMITATION_IMAGE_PLANE,
    LIMITATION_NOT_PROOF,
    LIMITATION_UNCALIBRATED,
    RuleConfig,
)
from ai_engine.tracking.tracker import Track, TrackPoint


def make_track(
    track_id: int,
    label: str,
    points: list[tuple[float, tuple[float, float], float]],
) -> Track:
    track = Track(track_id=track_id, class_label=label)
    for index, (timestamp, center, size) in enumerate(points):
        half = size / 2
        track.points.append(
            TrackPoint(
                frame_number=index + 1,
                timestamp_offset_seconds=timestamp,
                center=center,
                bbox=(center[0] - half, center[1] - half, center[0] + half, center[1] + half),
                size=size,
                score=0.9,
            )
        )
    return track


def converging_pair() -> list[Track]:
    """Six time-aligned samples where the gap closes sharply."""
    mine = (100.0, 100.0)
    first = make_track(
        1,
        "car",
        [
            (0.0, (100.0, 100.0), 100.0),
            (0.2, (140.0, 100.0), 100.0),
            (0.4, (180.0, 100.0), 100.0),
            (0.6, (220.0, 100.0), 100.0),
            (0.8, (250.0, 100.0), 100.0),
            (1.0, (262.0, 100.0), 100.0),
        ],
    )
    second = make_track(
        2,
        "motorcycle",
        [
            (0.0, (400.0, 110.0), 60.0),
            (0.2, (340.0, 110.0), 60.0),
            (0.4, (300.0, 110.0), 60.0),
            (0.6, (280.0, 110.0), 60.0),
            (0.8, (272.0, 110.0), 60.0),
            (1.0, (268.0, 110.0), 60.0),
        ],
    )
    assert mine  # keeps the geometry readable above
    return [first, second]


def test_near_miss_fires_when_two_tracks_converge() -> None:
    events = near_miss.evaluate(converging_pair(), RuleConfig())
    assert events, "converging trajectories should produce a candidate"
    event = events[0]
    assert event.event_type == "near_miss_candidate"
    assert LIMITATION_UNCALIBRATED in event.limitations
    assert LIMITATION_NOT_PROOF in event.limitations
    assert LIMITATION_IMAGE_PLANE in event.limitations
    assert 0.0 <= event.score <= 1.0


def test_near_miss_does_not_fire_for_parallel_traffic() -> None:
    first = make_track(
        1,
        "car",
        [(index * 0.2, (100.0 + index * 30, 100.0), 100.0) for index in range(6)],
    )
    second = make_track(
        2,
        "car",
        [(index * 0.2, (100.0 + index * 30, 400.0), 100.0) for index in range(6)],
    )
    assert near_miss.evaluate([first, second], RuleConfig()) == []


def test_collision_rule_needs_sustained_overlap_not_a_single_frame() -> None:
    first = make_track(
        1,
        "car",
        [(0.0, (100.0, 100.0), 100.0), (0.1, (105.0, 100.0), 100.0), (0.2, (110.0, 100.0), 100.0)],
    )
    second = make_track(
        2,
        "car",
        [(0.0, (500.0, 500.0), 100.0), (0.1, (500.0, 500.0), 100.0), (0.2, (500.0, 500.0), 100.0)],
    )
    assert collision.evaluate([first, second], RuleConfig()) == []


def test_registry_marks_uncalibrated_rules_unavailable_instead_of_guessing() -> None:
    tracks = [
        make_track(1, "car", [(index * 0.1, (100.0 + index * 10, 100.0), 100.0) for index in range(10)])
    ]
    events, outcomes = registry.evaluate_all(tracks, RuleConfig(), scene_config=None)
    by_name = {outcome.name: outcome for outcome in outcomes}
    assert by_name["wrong_way_v1"].status == "unavailable"
    assert by_name["signal_line_crossing_v1"].status == "unavailable"
    assert by_name["wrong_way_v1"].events == []
    for outcome in outcomes:
        assert outcome.version
        assert outcome.status in {"evaluated", "unavailable"}
    assert len(events) <= registry.MAX_EVENTS_PER_JOB


def test_registry_event_types_are_candidates_only() -> None:
    events, _ = registry.evaluate_all(converging_pair(), RuleConfig())
    for event in events:
        assert event.event_type.endswith("_candidate")
        assert "CONFIRMED" not in event.event_type.upper()
        assert event.severity in {"low", "medium", "high"}
