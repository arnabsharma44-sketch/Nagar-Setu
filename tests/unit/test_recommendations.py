"""Tests for the deterministic investigation draft and recommendation vocabulary.

The deterministic analyser is the default path (the LLM assistant is optional), so
its guarantees are pinned here: structured output, candidate-only language, and
human approval on every action.
"""

from __future__ import annotations

import pytest
from ai_engine.investigation.root_cause import (
    InvestigationInput,
    _dedupe,
    _dedupe_actions,
    draft_analysis,
)


def make_input(**overrides) -> InvestigationInput:
    values: dict = {
        "case_number": "INV-2024-001",
        "incident_type": "near_miss_candidate",
        "incident_source_kind": "ai_candidate",
        "incident_score": 0.75,
        "rule_name": "near_miss_v1",
        "rule_version": "1.0.0",
        "limitations": ["CAMERA_NOT_METRIC_CALIBRATED", "IMAGE_PLANE_MEASUREMENT_ONLY"],
        "asset_code": "ASSET-001",
        "asset_condition": "fair",
        "department_name": "DEMO Roads and Buildings",
        "responsibility_status": "matched_records",
        "contract_numbers": ["CONTRACT-001"],
        "contract_expired": False,
        "missing_records": ["No maintenance records for last 6 months"],
        "conflicts": [],
        "source_references": ["asset-reg-001", "contract-reg-001"],
        "review_status": "confirmed",
    }
    values.update(overrides)
    return InvestigationInput(**values)


@pytest.fixture
def investigation_input() -> InvestigationInput:
    return make_input()


class TestDeterministicAnalysis:
    def test_draft_analysis_produces_expected_structure(
        self, investigation_input: InvestigationInput
    ) -> None:
        result = draft_analysis(investigation_input)

        assert result["analysis_source"] == "deterministic"
        assert isinstance(result["observed_facts"], list) and result["observed_facts"]
        assert isinstance(result["potential_root_causes"], list)
        assert isinstance(result["missing_information"], list)
        assert isinstance(result["potentially_relevant_authorities"], list)
        assert isinstance(result["recommended_actions"], list)
        assert isinstance(result["limitations"], list)
        assert result["human_verification_required"] is True
        assert "model_name" in result
        assert "generated_at" in result

    def test_observed_facts_include_incident_details(
        self, investigation_input: InvestigationInput
    ) -> None:
        result = draft_analysis(investigation_input)
        facts_text = " ".join(result["observed_facts"])

        assert "near miss" in facts_text.lower()
        assert "confirmed" in facts_text.lower()
        assert "candidate observation" in facts_text.lower()

    def test_hypotheses_include_asset_condition_when_poor(self) -> None:
        result = draft_analysis(make_input(asset_condition="poor"))
        hypotheses_text = " ".join(
            hypothesis["hypothesis"] for hypothesis in result["potential_root_causes"]
        )
        assert "condition" in hypotheses_text.lower()
        assert "poor" in hypotheses_text.lower()

    def test_missing_information_includes_contract_expiry_note(self) -> None:
        result = draft_analysis(make_input(contract_expired=True))
        missing_text = " ".join(result["missing_information"]).lower()
        assert "maintenance agreement" in missing_text or "event date" in missing_text

    def test_actions_require_human_approval(
        self, investigation_input: InvestigationInput
    ) -> None:
        result = draft_analysis(investigation_input)
        assert result["recommended_actions"]
        for action in result["recommended_actions"]:
            assert action["requires_human_approval"] is True
            assert action["action"]
            assert action["rationale"]
            assert action["priority"]

    def test_limitations_always_include_core_limitations(
        self, investigation_input: InvestigationInput
    ) -> None:
        limitations = draft_analysis(investigation_input)["limitations"]
        assert "NO_PHYSICAL_SPEED_MEASUREMENT" in limitations
        assert "DETERMINISTIC_DRAFT_NOT_A_LEGAL_FINDING" in limitations
        assert "HUMAN_VERIFICATION_REQUIRED" in limitations


class TestDeduplication:
    def test_dedupe_strings_removes_duplicates(self) -> None:
        assert _dedupe(["a", "b", "a", "c", "b", "d"]) == ["a", "b", "c", "d"]

    def test_dedupe_empty_list(self) -> None:
        assert _dedupe([]) == []

    def test_dedupe_actions_removes_duplicate_actions(self) -> None:
        actions = [
            {"action": "Fix the road", "rationale": "R1", "priority": "high", "category": "repair"},
            {
                "action": "Fix the road",
                "rationale": "R2",
                "priority": "medium",
                "category": "repair",
            },
            {
                "action": "Paint lines",
                "rationale": "R3",
                "priority": "medium",
                "category": "marking",
            },
        ]
        result = _dedupe_actions(actions)
        assert len(result) == 2
        assert result[0]["action"] == "Fix the road"
        assert result[1]["action"] == "Paint lines"


class TestRecommendationWorkflow:
    def test_recommendation_statuses(self) -> None:
        from app.models import RecommendationStatus

        assert RecommendationStatus.DRAFT.value == "draft"
        assert RecommendationStatus.APPROVED.value == "approved"
        assert RecommendationStatus.REJECTED.value == "rejected"
        assert RecommendationStatus.SUPERSEDED.value == "superseded"

    def test_work_order_transitions_force_verification(self) -> None:
        from app.models import WORK_ORDER_TRANSITIONS, WorkOrderStatus

        assert WorkOrderStatus.ASSIGNED in WORK_ORDER_TRANSITIONS[WorkOrderStatus.PENDING]
        assert WorkOrderStatus.IN_PROGRESS not in WORK_ORDER_TRANSITIONS[WorkOrderStatus.PENDING]
        assert (
            WorkOrderStatus.COMPLETED_PENDING_VERIFICATION
            in WORK_ORDER_TRANSITIONS[WorkOrderStatus.IN_PROGRESS]
        )
        assert WorkOrderStatus.VERIFIED not in WORK_ORDER_TRANSITIONS[WorkOrderStatus.IN_PROGRESS]
        assert WORK_ORDER_TRANSITIONS[WorkOrderStatus.VERIFIED] == set()
        assert WORK_ORDER_TRANSITIONS[WorkOrderStatus.CANCELLED] == set()
