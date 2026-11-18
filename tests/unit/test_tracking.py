"""Tests for the tracking adapter."""

from __future__ import annotations

from ai_engine.detection.detector import Detection
from ai_engine.tracking.tracker import IouTracker, Track, TrackPoint, iou


def detection(
    frame: int, bbox: tuple[float, float, float, float], label: str = "car"
) -> Detection:
    return Detection(
        frame_number=frame,
        timestamp_offset_seconds=frame / 25.0,
        class_label=label,
        class_id=2,
        bbox=bbox,
        score=0.9,
    )


class TestIoU:
    def test_iou_is_one_for_identical_boxes(self) -> None:
        assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0

    def test_iou_is_zero_for_disjoint_boxes(self) -> None:
        assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0

    def test_iou_partial_overlap(self) -> None:
        assert 0.0 < iou((0, 0, 10, 10), (5, 5, 15, 15)) < 1.0


class TestIouTracker:
    def test_tracker_keeps_a_stable_id_across_overlapping_frames(self) -> None:
        tracker = IouTracker(iou_threshold=0.2)
        first = tracker.update([detection(1, (10, 10, 50, 50))])
        second = tracker.update([detection(2, (12, 12, 52, 52))])
        assert first[0][0] == second[0][0]

    def test_tracker_does_not_merge_different_classes(self) -> None:
        tracker = IouTracker(iou_threshold=0.2)
        first = tracker.update([detection(1, (10, 10, 50, 50), label="car")])
        second = tracker.update([detection(2, (10, 10, 50, 50), label="person")])
        assert first[0][0] != second[0][0]

    def test_tracker_assigns_new_ids_when_boxes_do_not_overlap(self) -> None:
        tracker = IouTracker(iou_threshold=0.3)
        first = tracker.update([detection(1, (0, 0, 20, 20))])
        second = tracker.update([detection(2, (200, 200, 220, 220))])
        assert first[0][0] != second[0][0]

    def test_finished_tracks_remain_available_to_event_rules(self) -> None:
        tracker = IouTracker(iou_threshold=0.2, max_missed_frames=1)
        tracker.update([detection(1, (0, 0, 20, 20))])
        tracker.update([detection(2, (500, 500, 520, 520))])
        tracker.update([detection(3, (900, 900, 920, 920))])
        retained = tracker.finalize()
        assert len(retained) == 3
        assert all(isinstance(track, Track) for track in retained)
        assert {track.frames for track in retained} == {1}

    def test_track_duration_and_speed_proxy_use_video_time_not_pixels(self) -> None:
        track = Track(track_id=1, class_label="car")
        track.points = [
            TrackPoint(1, 0.0, (0.0, 0.0), (0, 0, 10, 10), 10.0, 0.9),
            TrackPoint(2, 1.0, (50.0, 0.0), (40, 0, 60, 10), 10.0, 0.9),
        ]
        assert track.duration == 1.0
        assert track.displacement_per_second() == 50.0
        assert "image_plane_displacement_per_second" in track.as_summary()


class TestTrack:
    def test_track_summary_contains_expected_fields(self) -> None:
        track = Track(track_id=42, class_label="car")
        track.points = [
            TrackPoint(1, 0.0, (0.0, 0.0), (0, 0, 10, 10), 10.0, 0.9),
            TrackPoint(2, 0.1, (10.0, 0.0), (5, 0, 15, 10), 10.0, 0.9),
        ]
        summary = track.as_summary()
        assert summary["track_id"] == 42
        assert summary["class_label"] == "car"
        assert summary["frames"] == 2
        assert summary["start_offset_seconds"] == 0.0
        assert summary["end_offset_seconds"] == 0.1
        assert "image_plane_displacement_per_second" in summary