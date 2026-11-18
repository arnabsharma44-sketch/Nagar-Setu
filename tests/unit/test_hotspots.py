"""Tests for hotspot analysis."""

from __future__ import annotations

import pytest
from datetime import UTC, datetime
from unittest.mock import Mock, patch
import numpy as np

from app.services.analytics import _collect_records, _label_for, analyze, to_feature_collection
from app.models import AccidentRecord, Incident, IncidentSourceKind, IncidentType, ReviewStatus
from sqlalchemy import select


class TestHotspotAnalysis:
    @pytest.fixture
    def mock_session(self):
        session = Mock()
        return session

    def test_collect_records_separates_sources(self, mock_session):
        mock_accident = Mock(spec=AccidentRecord)
        mock_accident.id = "acc-1"
        mock_accident.latitude = 20.2961
        mock_accident.longitude = 85.8245
        mock_accident.accident_time = datetime.now(UTC)
        mock_accident.accident_type = "collision"
        mock_accident.source_name = "police"
        mock_accident.source_reference = "ref-1"

        mock_incident = Mock(spec=Incident)
        mock_incident.id = "inc-1"
        mock_incident.latitude = 20.2961
        mock_incident.longitude = 85.8245
        mock_incident.event_time = datetime.now(UTC)
        mock_incident.incident_type = IncidentType.NEAR_MISS_CANDIDATE
        mock_incident.review_status = ReviewStatus.CONFIRMED

        mock_session.execute.return_value.scalars.return_value = [mock_accident, mock_incident]

        with patch("app.services.analytics.select") as mock_select:
            mock_select.return_value.where.return_value = mock_select.return_value
            records, unlocated = _collect_records(mock_session, None, None)

        assert len(records) == 2
        sources = {r["source"] for r in records}
        assert "historical_accident_records" in sources
        assert "human_confirmed_observations" in sources

    def test_unlocated_count_is_reported(self, mock_session):
        mock_session.execute.return_value.scalar_one.return_value = 5
        records, unlocated = _collect_records(Mock(), None, None)
        assert unlocated == 5

    def test_label_for_historical_and_confirmed(self) -> None:
        counts = {"historical_accident_records": 3, "human_confirmed_observations": 2}
        label = _label_for(counts)
        assert "Historical accidents and confirmed observations concentrated" in label

    def test_label_for_historical_only(self) -> None:
        counts = {"historical_accident_records": 3}
        label = _label_for(counts)
        assert "Historical accident record concentration" in label

    def test_label_for_confirmed_only(self) -> None:
        counts = {"human_confirmed_observations": 2}
        label = _label_for(counts)
        assert "Confirmed observation concentration" in label

    def test_label_for_ai_only(self) -> None:
        counts = {"pending_ai_candidates": 5}
        label = _label_for(counts)
        assert "Unreviewed AI candidate concentration" in label
        assert "not an accident count" in label


class TestToFeatureCollection:
    def test_to_feature_collection_creates_valid_geojson(self) -> None:
        from app.services.analytics import to_feature_collection
        from app.models import HotspotAnalysis

        analysis = Mock(spec=HotspotAnalysis)
        analysis.id = "test-id"
        analysis.method = "dbscan"
        analysis.radius_meters = 250.0
        analysis.window_from = None
        analysis.window_to = None
        analysis.generated_at = datetime.now(UTC)
        analysis.results = {
            "clusters": [
                {
                    "cluster_key": "cluster-1",
                    "latitude": 20.2961,
                    "longitude": 85.8245,
                    "radius_meters": 250.0,
                    "counts": {"historical_accident_records": 2},
                    "total_records": 2,
                    "categories": {"collision": 2},
                    "first_seen": "2024-01-01T00:00:00Z",
                    "last_seen": "2024-12-31T23:59:59Z",
                    "record_ids": ["rec-1", "rec-2"],
                    "label": "Test cluster",
                }
            ],
            "methodology_note": "Test note",
            "unlocated_count": 0,
        }
        analysis.is_demo = True

        fc = to_feature_collection(analysis)
        assert fc.type == "FeatureCollection"
        assert len(fc.features) == 1
        feature = fc.features[0]
        assert feature.type == "Feature"
        assert feature.geometry.type == "Point"
        assert feature.geometry.coordinates == [85.8245, 20.2961]
        assert feature.properties["cluster_key"] == "cluster-1"
        assert feature.properties["counts_by_source"] == {"historical_accident_records": 2}

    def test_empty_analysis_returns_empty_features(self) -> None:
        from app.services.analytics import to_feature_collection
        from app.models import HotspotAnalysis

        analysis = Mock(spec=HotspotAnalysis)
        analysis.results = {"clusters": [], "unlocated_count": 0}
        analysis.generated_at = datetime.now(UTC)
        analysis.method = "dbscan"
        analysis.methodology_note = "Test"
        analysis.data_sources = ["historical_accident_records"]

        fc = to_feature_collection(analysis)
        assert fc.type == "FeatureCollection"
        assert len(fc.features) == 0