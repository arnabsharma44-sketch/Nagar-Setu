"""Unit tests for hotspot analysis.

The tests drive ``_collect_records`` and ``to_feature_collection`` with a stub
session that returns results in the exact order the service asks for them, so the
source-separation logic itself is exercised.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.models import (
    AccidentRecord,
    HotspotAnalysis,
    Incident,
    IncidentType,
    ReviewStatus,
)
from app.services.analytics import _collect_records, _label_for, to_feature_collection


class _Result:
    def __init__(self, *, rows: list | None = None, scalar: int = 0) -> None:
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self) -> _Result:
        return self

    def all(self) -> list:
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)

    def scalar_one(self) -> int:
        return self._scalar


class StubSession:
    def __init__(self, *results: _Result) -> None:
        self._results = list(results)
        self.execute_calls = 0

    def execute(self, statement):  # noqa: ANN001, ARG002
        result = self._results[self.execute_calls]
        self.execute_calls += 1
        return result


def located_accident() -> AccidentRecord:
    return AccidentRecord(
        id=uuid4(),
        organization_id=uuid4(),
        accident_type="rear_end",
        latitude=20.2961,
        longitude=85.8245,
        accident_time=datetime(2024, 5, 1, 9, 30, tzinfo=UTC),
        source_name="Traffic Police",
        source_reference="ref-1",
    )


def located_incident() -> Incident:
    return Incident(
        id=uuid4(),
        organization_id=uuid4(),
        incident_type=IncidentType.NEAR_MISS_CANDIDATE,
        review_status=ReviewStatus.CONFIRMED,
        latitude=20.2961,
        longitude=85.8245,
        event_time=datetime(2024, 5, 2, 18, 0, tzinfo=UTC),
    )


class TestHotspotAnalysis:
    def test_collect_records_separates_sources(self) -> None:
        session = StubSession(
            _Result(rows=[located_accident()]),
            _Result(scalar=0),
            _Result(rows=[located_incident()]),
            _Result(scalar=0),
        )

        records, unlocated = _collect_records(session, None, None)  # type: ignore[arg-type]

        assert len(records) == 2
        sources = {record["source"] for record in records}
        assert sources == {"historical_accident_records", "human_confirmed_observations"}
        assert unlocated == 0

    def test_unlocated_count_is_reported(self) -> None:
        session = StubSession(
            _Result(rows=[]),
            _Result(scalar=5),
            _Result(rows=[]),
            _Result(scalar=0),
        )

        records, unlocated = _collect_records(session, None, None)  # type: ignore[arg-type]

        assert records == []
        assert unlocated == 5

    def test_label_for_historical_and_confirmed(self) -> None:
        counts = {"historical_accident_records": 3, "human_confirmed_observations": 2}
        assert "Historical accidents and confirmed observations concentrated" in _label_for(counts)

    def test_label_for_historical_only(self) -> None:
        assert "Historical accident record concentration" in _label_for(
            {"historical_accident_records": 3}
        )

    def test_label_for_confirmed_only(self) -> None:
        assert "Confirmed observation concentration" in _label_for(
            {"human_confirmed_observations": 2}
        )

    def test_label_for_ai_only(self) -> None:
        label = _label_for({"pending_ai_candidates": 5})
        assert "Unreviewed AI candidate concentration" in label
        assert "not an accident count" in label


def stored_analysis(clusters: list[dict]) -> HotspotAnalysis:
    return HotspotAnalysis(
        id=uuid4(),
        organization_id=uuid4(),
        method="dbscan_haversine_combined_layers",
        radius_meters=250.0,
        min_size=2,
        window_from=None,
        window_to=None,
        results={
            "clusters": clusters,
            "unlocated_count": 0,
            "methodology_note": "Test note",
        },
        generated_at=datetime(2024, 6, 1, tzinfo=UTC),
        is_demo=True,
    )


class TestToFeatureCollection:
    def test_to_feature_collection_creates_valid_geojson(self) -> None:
        analysis = stored_analysis(
            [
                {
                    "cluster_key": "cluster-1",
                    "latitude": 20.2961,
                    "longitude": 85.8245,
                    "radius_meters": 250.0,
                    "counts": {"historical_accident_records": 2},
                    "total_records": 2,
                    "source_mix": ["historical_accident_records"],
                    "categories": {"rear_end": 2},
                    "first_seen": "2024-01-01T00:00:00Z",
                    "last_seen": "2024-12-31T23:59:59Z",
                    "record_ids": [str(uuid4()), str(uuid4())],
                    "label": "Test cluster",
                }
            ]
        )

        feature_collection = to_feature_collection(analysis)

        assert feature_collection.type == "FeatureCollection"
        assert len(feature_collection.features) == 1
        feature = feature_collection.features[0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [85.8245, 20.2961]
        assert feature["properties"]["cluster_key"] == "cluster-1"
        assert feature["properties"]["counts_by_source"] == {"historical_accident_records": 2}

    def test_empty_analysis_returns_empty_features(self) -> None:
        collection = to_feature_collection(stored_analysis([]))
        assert collection.type == "FeatureCollection"
        assert collection.features == []
