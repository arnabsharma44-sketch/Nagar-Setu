"""Tests for event detection rules."""

from __future__ import annotations

from ai_engine.events import collision, near_miss, pedestrian_conflict, rapid_motion
from ai_engine.events.base import RuleConfig
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
    def test_pedestrian_conflict_fires_for_vehicle_person_proximity(self) -> None:
        from ai_engine.events import pedestrian_conflict
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
        events = pedestrian_conflict.evaluate([vehicle, person], RuleConfig())
        assert events
        event = events[0]
        assert event.event_type == "pedestrian_conflict_candidate"

    def test_pedestrian_conflict_does_not_fire_for_vehicle_vehicle(self) -> None:
        from ai_engine.events import pedestrian_conflict
        first = make_track(1, "car", [(index * 0.1, (100.0 + index * 20, 100.0), 100.0) for index in range(20)])
        second = make_track(2, "car", [(index * 0.1, (100.0 + index * 20, 300.0), 100.0) for index in range(20)])
        assert pedestrian_conflict.evaluate([first, second], RuleConfig()) == []


class TestRapidMotion:
    def test_rapid_motion_fires_for_sudden_acceleration(self) -> None:
        from ai_engine.events import rapid_motion
        track = make_track(
            1,
            "car",
            [
                (0.0, (100.0, 100.0), 100.0),
                (0.1, (105.0, 100.0), 100.0),
                (0.2, (120.0, 100.0), 100.0),
                (0.3, (150.0, 100.0), 100.0),
                (0.4, (200.0, 100.0), 100.0),
            ],
        )
        events = rapid_motion.evaluate([track], RuleConfig())
        assert events
        event = events[0]
        assert event.event_type == "rapid_motion_candidate"

    def test_rapid_motion_does_not_fire_for_constant_velocity(self) -> None:
        from ai_engine.events import rapid_motion
        track = make_track(
            1,
            "car",
            [(index * 0.1, (100.0 + index * 10, 100.0), 100.0) for index in range(20)],
        )
        assert rapid_motion.evaluate([track], RuleConfig()) == []


class TestWrongWay:
    def test_wrong_way_unavailable_without_scene_config(self) -> None:
        from ai_engine.events import registry
        track = make_track(1, "car", [(index * 0.1, (100.0 + index * 20, 100.0), 100.0) for index in range(20)])
        events, outcomes = registry.evaluate_all([track], RuleConfig(), scene_config=None)
        by_name = {o.name: o for o in outcomes}
        assert by_name["wrong_way_v1"].status == "unavailable"
        assert by_name["wrong_way_v1"].events == []


class TestSignalViolation:
    def test_signal_violation_unavailable_without_scene_config(self) -> None:
        from ai_engine.events import registry
        track = make_track(1, "car", [(index * 0.1, (100.0 + index * 20, 100.0), 100.0) for index in range(20)])
        events, outcomes = registry.evaluate_all([track], RuleConfig(), scene_config=None)
        by_name = {o.name: o for o in outcomes}
        assert by_name["signal_line_crossing_v1"].status == "unavailable"
        assert by_name["signal_line_crossing_v1"].events == []


class TestRegistry:
    def test_registry_max_events_per_job(self) -> None:
        from ai_engine.events import registry
        tracks = [make_track(i, "car", [(0.0, (100.0 + i * 100, 100.0), 100.0)]) for i in range(50)]
        events, _ = registry.evaluate_all(tracks, RuleConfig())
        from ai_engine.events.registry import MAX_EVENTS_PER_JOB
        assert len(events) <= MAX_EVENTS_PER_JOB

    def test_registry_event_types_are_candidates_only(self) -> None:
        from ai_engine.events import registry
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

    def test_near_miss_does_not_fire_for_insufficient_track_length(self) -> None:
        first = make_track(1, "car", [(0.0, (100.0, 100.0), 100.0)])
        second = make_track(2, "car", [(0.0, (200.0, 100.0), 100.0)])
        assert near_miss.evaluate([first, second], RuleConfig()) == []


class TestCollision:
    def test_collision_rule_needs_sustained_overlap_not_a_single_frame(self) -> None:
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

    def test_collision_fires_on_sustained_overlap(self) -> None:
        first = make_track(
            1,
            "car",
            [
                (0.0, (100.0, 100.0), 100.0),
                (0.1, (105.0, 100.0), 100.0),
                (0.2, (110.0, 100.0), 100.0),
                (0.3, (115.0, 100.0), 100.0),
            ],
        )
        second = make_track(
            2,
            "car",
            [
                (0.0, (100.0, 100.0), 100.0),
                (0.1, (105.0, 100.0), 100.0),
                (0.2, (110.0, 100.0), 100.0),
                (0.3, (115.0, 100.0), 100.0),
            ],
        )
        events = collision.evaluate([first, second], RuleConfig())
        assert events
        event = events[0]
        assert event.event_type == "collision_candidate"