"""Tests for recommendation logic."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from app.models import (
    Asset, AssetType, ConditionStatus, Contract, ContractAsset, Contractor,
    Department, Investigation, InvestigationStatus, LocationQuality,
    Recommendation, RecommendationStatus, Severity, WorkOrder, WorkOrderStatus,
)
from ai_engine.investigation.root_cause import InvestigationInput, draft_analysis, _dedupe, _dedupe_actions


class TestDeterministicAnalysis:
    @pytest.fixture
    def investigation_input(self):
        return InvestigationInput(
            case_number="INV-2024-001",
            incident_type="near_miss_candidate",
            incident_source_kind="ai_candidate",
            incident_score=0.75,
            rule_name="near_miss_v1",
            rule_version="1.0.0",
            limitations=["CAMERA_NOT_METRIC_CALIBRATED", "IMAGE_PLANE_MEASUREMENT_ONLY"],
            asset_code="ASSET-001",
            asset_condition="FAIR",
            department_name="DEMO Roads and Buildings",
            responsibility_status="matched_records",
            contract_numbers=["CONTRACT-001"],
            contract_expired=False,
            missing_records=["No maintenance records for last 6 months"],
            conflicts=[],
            source_references=["asset-reg-001", "contract-reg-001"],
            review_status="confirmed",
        )

    def test_draft_analysis_produces_expected_structure(self, investigation_input):
        result = draft_analysis(investigation_input)

        assert "analysis_source" in result
        assert result["analysis_source"] == "deterministic"
        assert "observed_facts" in result
        assert isinstance(result["observed_facts"], list)
        assert len(result["observed_facts"]) > 0

        assert "potential_root_causes" in result
        assert isinstance(result["potential_root_causes"], list)

        assert "missing_information" in result
        assert isinstance(result["missing_information"], list)

        assert "potentially_relevant_authorities" in result
        assert isinstance(result["potentially_relevant_authorities"], list)

        assert "recommended_actions" in result
        assert isinstance(result["recommended_actions"], list)

        assert "limitations" in result
        assert isinstance(result["limitations"], list)

        assert result["human_verification_required"] is True
        assert "model_name" in result
        assert "generated_at" in result

    def test_observed_facts_include_incident_details(self, investigation_input):
        result = draft_analysis(investigation_input)
        facts_text = " ".join(result["observed_facts"])
        assert "near_miss_candidate" in facts_text
        assert "confirmed" in facts_text.lower()
        assert "asset" in facts_text.lower() or "ASSET-001" in facts_text

    def test_hypotheses_include_asset_condition_when_poor(self):
        input_poor = InvestigationInput(
            case_number="INV-2024-002",
            incident_type="collision_candidate",
            incident_source_kind="ai_candidate",
            incident_score=0.9,
            rule_name="collision_v1",
            rule_version="1.0.0",
            limitations=["CAMERA_NOT_METRIC_CALIBRATED"],
            asset_code="ASSET-002",
            asset_condition="POOR",
            department_name="DEMO Roads",
            responsibility_status="matched_records",
            contract_numbers=["CON-001"],
            contract_expired=False,
            missing_records=[],
            conflicts=[],
            source_references=["asset-reg-002"],
            review_status="confirmed",
        )
        result = draft_analysis(input_poor)
        hypotheses_text = " ".join(h["hypothesis"] for h in result["potential_root_causes"])
        assert "condition" in hypotheses_text.lower() or "POOR" in hypotheses_text

class TestDeduplication:
    def test_dedupe_strings_removes_duplicates(self) -> None:
        from ai_engine.investigation.root_cause import _dedupe
        values = ["a", "b", "a", "c", "b", "d"]
        result = _dedupe(values)
        assert result == ["a", "b", "c", "d"]

    def test_dedupe_empty_list(self) -> None:
        from ai_engine.investigation.root_cause import _dedupe
        assert _dedupe([]) == []

    def test_dedupe_actions_removes_duplicate_actions(self) -> None:
        from ai_engine.investigation.root_cause import _dedupe_actions
        actions = [
            {"action": "Fix the road", "rationale": "R1", "priority": "high", "category": "repair"},
            {"action": "Fix the road", "rationale": "R2", "priority": "medium", "category": "repair"},
            {"action": "Paint lines", "rationale": "R3", "priority": "medium", "category": "marking"},
        ]
        result = _dedupe_actions(actions)
        assert len(result) == 2
        assert result[0]["action"] == "Fix the road"
        assert result[1]["action"] == "Paint lines"


class TestRecommendationWorkflow:
    def test_recommendation_workflow_statuses(self) -> None:
        from app.models import RecommendationStatus
        assert RecommendationStatus.DRAFT.value == "draft"
        assert RecommendationStatus.APPROVED.value == "approved"
        assert RecommendationStatus.REJECTED.value == "rejected"
        assert RecommendationStatus.SUPERSEDED.value == "superseded"

    def test_work_order_status_transitions(self) -> None:
        from app.models import WorkOrderStatus, WORK_ORDER_TRANSITIONS
        assert WorkOrderStatus.PENDING in WORK_ORDER_TRANSITIONS
        assert WorkOrderStatus.ASSIGNED in WORK_ORDER_TRANSITIONS[WorkOrderStatus.PENDING]
        assert WorkOrderStatus.IN_PROGRESS not in WORK_ORDER_TRANSITIONS[WorkOrderStatus.PENDING]
        assert WorkOrderStatus.COMPLETED_PENDING_VERIFICATION in WORK_ORDER_TRANSITIONS[WorkOrderStatus.IN_PROGRESS]
        assert WorkOrderStatus.VERIFIED not in WORK_ORDER_TRANSITIONS[WorkOrderStatus.IN_PROGRESS]
        assert WORK_ORDER_TRANSITIONS[WorkOrderStatus.VERIFIED] == set()
        assert WORK_ORDER_TRANSITIONS[WorkOrderStatus.CANCELLED] == set()
    def test_missing_information_includes_contract_expiry_note(self, investigation_input):
        investigation_input.contract_expired = True
        result = draft_analysis(investigation_input)
        missing_text = " ".join(result["missing_information"])
        assert "contract" in missing_text.lower() or "expired" in missing_text.lower()

    def test_actions_require_human_approval(self, investigation_input):
        result = draft_analysis(investigation_input)
        for action in result["recommended_actions"]:
            assert action["requires_human_approval"] is True
            assert "action" in action
            assert "rationale" in action
            assert "priority" in action

    def test_limitations_always_include_core_limitations(self, investigation_input):
        result = draft_analysis(investigation_input)
        limitations = result["limitations"]
        assert "NO_PHYSICAL_SPEED_MEASUREMENT" in limitations
        assert "DETERMINISTIC_DRAFT_NOT_A_LEGAL_FINDING" in limitations
        assert "HUMAN_VERIFICATION_REQUIRED" in limitations