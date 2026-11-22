"""Tests for the candidate event rules.

Every rule is a heuristic over image-plane geometry. These tests pin down when a
rule fires and — more importantly — when it must stay silent.
"""

from __future__ import annotations

from ai_engine.events import collision, near_miss, pedestrian_conflict, rapid_motion, registry
from ai_engine.events.base import RuleConfig
from ai_engine.events.registry import MAX_EVENTS_PER_JOB
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
    return [first, second]


class TestPedestrianConflict:
    def test_pedestrian_conflict_fires_when_a_person_closes_on_a_vehicle(self) -> None:
        vehicle = make_track(
            1,
            "car",
            [(index * 0.1, (100.0, 100.0), 100.0) for index in range(20)],
        )
        person = make_track(
            2,
            "person",
            [(index * 0.1, (300.0 - index * 10, 100.0), 40.0) for index in range(20)],
        )

        events = pedestrian_conflict.evaluate([vehicle, person], RuleConfig())

        assert events, "a person walking into a vehicle's path is a conflict candidate"
        event = events[0]
        assert event.event_type == "pedestrian_vehicle_conflict_candidate"
        assert "PERSON_NOT_IDENTIFIED" in event.limitations
        assert 0.0 <= event.score <= 1.0

    def test_pedestrian_conflict_does_not_fire_for_constant_separation(self) -> None:
        """Walking parallel at a fixed offset is traffic, not a conflict."""
        vehicle = make_track(
            1,
            "car",
            [(index * 0.1, (100.0 + index * 20, 100.0), 100.0) for index in range(20)],
        )
        person = make_track(
            2,
            "person",
            [(index * 0.1, (100.0 + index * 20, 105.0), 40.0) for index in range(20)],
        )
        assert pedestrian_conflict.evaluate([vehicle, person], RuleConfig()) == []

    def test_pedestrian_conflict_does_not_fire_for_vehicle_vehicle(self) -> None:
        first = make_track(
            1, "car", [(index * 0.1, (100.0 + index * 20, 100.0), 100.0) for index in range(20)]
        )
        second = make_track(
            2, "car", [(index * 0.1, (100.0 + index * 20, 300.0), 100.0) for index in range(20)]
        )
        assert pedestrian_conflict.evaluate([first, second], RuleConfig()) == []


class TestRapidMotion:
    def test_rapid_motion_fires_for_sudden_deceleration(self) -> None:
        # The rule needs at least six samples: moving fast, then nearly stationary.
        track = make_track(
            1,
            "car",
            [
                (0.0, (100.0, 100.0), 100.0),
                (0.1, (140.0, 100.0), 100.0),
                (0.2, (180.0, 100.0), 100.0),
                (0.3, (220.0, 100.0), 100.0),
                (0.4, (221.0, 100.0), 100.0),
                (0.5, (222.0, 100.0), 100.0),
                (0.6, (223.0, 100.0), 100.0),
                (0.7, (224.0, 100.0), 100.0),
            ],
        )
        events = rapid_motion.evaluate([track], RuleConfig())
        assert events
        assert events[0].event_type == "rapid_motion_change_candidate"
        assert "NOT_A_BRAKING_MEASUREMENT" in events[0].limitations

    def test_rapid_motion_does_not_fire_for_constant_velocity(self) -> None:
        track = make_track(
            1,
            "car",
            [(index * 0.1, (100.0 + index * 10, 100.0), 100.0) for index in range(20)],
        )
        assert rapid_motion.evaluate([track], RuleConfig()) == []


class TestWrongWay:
    def test_wrong_way_unavailable_without_scene_config(self) -> None:
        track = make_track(
            1, "car", [(index * 0.1, (100.0 + index * 20, 100.0), 100.0) for index in range(20)]
        )
        events, outcomes = registry.evaluate_all([track], RuleConfig(), scene_config=None)
        by_name = {outcome.name: outcome for outcome in outcomes}
        assert by_name["wrong_way_v1"].status == "unavailable"
        assert by_name["wrong_way_v1"].events == []


class TestSignalViolation:
    def test_signal_violation_unavailable_without_scene_config(self) -> None:
        track = make_track(
            1, "car", [(index * 0.1, (100.0 + index * 20, 100.0), 100.0) for index in range(20)]
        )
        events, outcomes = registry.evaluate_all([track], RuleConfig(), scene_config=None)
        by_name = {outcome.name: outcome for outcome in outcomes}
        assert by_name["signal_line_crossing_v1"].status == "unavailable"
        assert by_name["signal_line_crossing_v1"].events == []


class TestRegistry:
    def test_registry_max_events_per_job(self) -> None:
        tracks = [
            make_track(index, "car", [(0.0, (100.0 + index * 100, 100.0), 100.0)])
            for index in range(50)
        ]
        events, _ = registry.evaluate_all(tracks, RuleConfig())
        assert len(events) <= MAX_EVENTS_PER_JOB

    def test_registry_event_types_are_candidates_only(self) -> None:
        events, _ = registry.evaluate_all(converging_pair(), RuleConfig())
        for event in events:
            assert event.event_type.endswith("_candidate")
            assert "CONFIRMED" not in event.event_type.upper()
            assert event.severity in {"low", "medium", "high"}


class TestNearMiss:
    def test_near_miss_fires_when_two_tracks_converge(self) -> None:
        events = near_miss.evaluate(converging_pair(), RuleConfig())
        assert events, "converging trajectories should produce a candidate"
        event = events[0]
        assert event.event_type == "near_miss_candidate"
        assert "CAMERA_NOT_METRIC_CALIBRATED" in event.limitations
        assert "CANDIDATE_OBSERVATION_NOT_CONFIRMED_EVENT" in event.limitations
        assert "IMAGE_PLANE_MEASUREMENT_ONLY" in event.limitations
        assert 0.0 <= event.score <= 1.0

    def test_near_miss_does_not_fire_for_parallel_traffic(self) -> None:
        first = make_track(
            1, "car", [(index * 0.2, (100.0 + index * 30, 100.0), 100.0) for index in range(6)]
        )
        second = make_track(
            2, "car", [(index * 0.2, (100.0 + index * 30, 400.0), 100.0) for index in range(6)]
        )
        assert near_miss.evaluate([first, second], RuleConfig()) == []

    def test_near_miss_does_not_fire_for_insufficient_track_length(self) -> None:
        first = make_track(1, "car", [(0.0, (100.0, 100.0), 100.0)])
        second = make_track(2, "car", [(0.0, (200.0, 100.0), 100.0)])
        assert near_miss.evaluate([first, second], RuleConfig()) == []


class TestCollision:
    def test_collision_rule_needs_sustained_overlap_not_a_single_frame(self) -> None:
        first = make_track(
            1,
            "car",
            [
                (0.0, (100.0, 100.0), 100.0),
                (0.1, (105.0, 100.0), 100.0),
                (0.2, (110.0, 100.0), 100.0),
            ],
        )
        second = make_track(
            2,
            "car",
            [
                (0.0, (500.0, 500.0), 100.0),
                (0.1, (500.0, 500.0), 100.0),
                (0.2, (500.0, 500.0), 100.0),
            ],
        )
        assert collision.evaluate([first, second], RuleConfig()) == []

    def test_collision_fires_when_overlap_follows_a_motion_stop(self) -> None:
        # Extreme proximity alone is not enough: the rule also needs the approach
        # to stop after the closest point. A parked car and a car that drives into
        # it and stops satisfies both conditions.
        first = make_track(
            1,
            "car",
            [
                (0.0, (100.0, 100.0), 100.0),
                (0.1, (130.0, 100.0), 100.0),
                (0.2, (160.0, 100.0), 100.0),
                (0.3, (190.0, 100.0), 100.0),
                (0.4, (200.0, 100.0), 100.0),
                (0.5, (200.0, 100.0), 100.0),
                (0.6, (200.0, 100.0), 100.0),
                (0.7, (200.0, 100.0), 100.0),
            ],
        )
        second = make_track(
            2,
            "car",
            [(index * 0.1, (200.0, 100.0), 100.0) for index in range(8)],
        )

        events = collision.evaluate([first, second], RuleConfig())

        assert events
        assert events[0].event_type == "collision_candidate"
        assert "COLLISION_CLAIM_REQUIRES_HUMAN_REVIEW" in events[0].limitations
