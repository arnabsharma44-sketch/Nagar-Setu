"""Deterministic investigation draft.

This module produces the same structured shape as the optional LLM assistant using
only the supplied records. Every hypothesis names the record ids that support it,
every action requires human approval, and nothing here decides liability.

The application must remain fully usable when no LLM key is configured, so this is
the default analysis source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

ANALYSIS_VERSION = "deterministic_rules_v1"

APPROVED_ACTION_CATEGORIES = [
    "field_inspection",
    "asset_condition_review",
    "maintenance_record_review",
    "signage_or_marking_review",
    "signal_timing_review",
    "further_cctv_review",
    "responsibility_record_correction",
]


@dataclass
class InvestigationInput:
    case_number: str
    incident_type: str | None = None
    incident_source_kind: str | None = None
    incident_score: float | None = None
    rule_name: str | None = None
    rule_version: str | None = None
    limitations: list[str] = field(default_factory=list)
    asset_code: str | None = None
    asset_condition: str | None = None
    asset_id: str | None = None
    department_name: str | None = None
    responsibility_status: str | None = None
    contract_numbers: list[str] = field(default_factory=list)
    contract_expired: bool = False
    missing_records: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    source_references: list[str] = field(default_factory=list)
    review_status: str | None = None


def draft_analysis(payload: InvestigationInput) -> dict[str, Any]:
    observed_facts: list[str] = []
    hypotheses: list[dict[str, Any]] = []
    missing_information: list[str] = []
    actions: list[dict[str, Any]] = []
    limitations: list[str] = []

    if payload.incident_type:
        observed_facts.append(
            f"A {payload.incident_type.replace('_', ' ')} record is linked to this case"
            + (f" with review status '{payload.review_status}'." if payload.review_status else ".")
        )
    if payload.incident_source_kind == "ai_candidate":
        observed_facts.append(
            "The linked observation was produced by the configured detection rule "
            f"{payload.rule_name or 'unknown'} v{payload.rule_version or 'unknown'} and is a "
            "candidate observation pending human review."
        )
    if payload.incident_score is not None:
        observed_facts.append(
            f"Recorded model score is {payload.incident_score:.2f}; this is a model-specific "
            "score, not a probability that an accident occurred."
        )
    if payload.asset_code:
        observed_facts.append(
            f"Asset {payload.asset_code} is linked to this case"
            + (f" with recorded condition '{payload.asset_condition}'." if payload.asset_condition else ".")
        )
    if payload.department_name:
        observed_facts.append(
            f"Records indicate {payload.department_name} as the maintaining department for the asset."
        )
    if payload.contract_numbers:
        observed_facts.append(
            "Linked contract records: " + ", ".join(sorted(payload.contract_numbers)) + "."
        )

    if payload.contract_expired:
        hypotheses.append(
            {
                "hypothesis": (
                    "The recorded maintenance contract may not have been in effect at the event date; "
                    "a replacement or extension record may exist outside this system."
                ),
                "supporting_record_ids": payload.contract_numbers,
                "counter_evidence": [],
                "confidence_label": "low",
            }
        )
        missing_information.append(
            "Confirm which maintenance agreement was in effect on the event date."
        )
        actions.append(
            {
                "action": "Review contract coverage dates and attach the effective agreement record.",
                "rationale": "Contract dates recorded here do not cover the event date.",
                "priority": "high",
                "category": "maintenance_record_review",
                "requires_human_approval": True,
            }
        )
    if payload.asset_condition in {"poor", "fair"}:
        hypotheses.append(
            {
                "hypothesis": (
                    f"Recorded asset condition '{payload.asset_condition}' for "
                    f"{payload.asset_code or 'the linked asset'} may be relevant to the observed "
                    "event. This is an unverified hypothesis."
                ),
                "supporting_record_ids": [payload.asset_id] if payload.asset_id else [],
                "counter_evidence": [],
                "confidence_label": "low",
            }
        )
        actions.append(
            {
                "action": "Conduct a field inspection of the linked asset and record current condition.",
                "rationale": "The asset register records a condition that may warrant inspection.",
                "priority": "medium",
                "category": "field_inspection",
                "requires_human_approval": True,
            }
        )
    if payload.responsibility_status in {
        "no_asset_match",
        "missing_contract_data",
        "requires_field_verification",
        "ambiguous_match",
    }:
        hypotheses.append(
            {
                "hypothesis": (
                    "Responsibility records are incomplete for this location, so no single "
                    "authority can be identified from the register alone. This is not a finding "
                    "of fault."
                ),
                "supporting_record_ids": payload.source_references,
                "counter_evidence": [],
                "confidence_label": "low",
            }
        )
        missing_information.append(
            "Establish which authority's records cover this location for the event date."
        )
        actions.append(
            {
                "action": "Verify asset ownership and maintenance responsibility in the field.",
                "rationale": "The asset/contract register does not resolve a single responsible record.",
                "priority": "high",
                "category": "responsibility_record_correction",
                "requires_human_approval": True,
            }
        )

    if payload.incident_type in {"near_miss_candidate", "collision_candidate"}:
        actions.append(
            {
                "action": "Review signage, road markings and sight lines at the recorded location.",
                "rationale": (
                    "The linked record is a road-user conflict candidate; a site review is a "
                    "reasonable next step before any corrective work is proposed."
                ),
                "priority": "medium",
                "category": "signage_or_marking_review",
                "requires_human_approval": True,
            }
        )
    if payload.incident_type == "pedestrian_vehicle_conflict_candidate":
        actions.append(
            {
                "action": "Review the pedestrian crossing layout and visibility at this location.",
                "rationale": "A vulnerable road user conflict candidate was recorded.",
                "priority": "high",
                "category": "signage_or_marking_review",
                "requires_human_approval": True,
            }
        )
    if payload.incident_source_kind == "ai_candidate":
        actions.append(
            {
                "action": "Review additional footage from the same camera and time window.",
                "rationale": "A single candidate observation is not sufficient evidence on its own.",
                "priority": "low",
                "category": "further_cctv_review",
                "requires_human_approval": True,
            }
        )

    for item in payload.missing_records:
        missing_information.append(item)
    for item in payload.conflicts:
        missing_information.append(f"Record conflict to resolve: {item}")

    limitations.extend(payload.limitations or [])
    limitations.extend(
        [
            "NO_PHYSICAL_SPEED_MEASUREMENT",
            "DETERMINISTIC_DRAFT_NOT_A_LEGAL_FINDING",
            "HUMAN_VERIFICATION_REQUIRED",
        ]
    )

    if not missing_information:
        missing_information.append(
            "Confirm the event date, location and asset condition with a field officer."
        )

    return {
        "analysis_source": "deterministic",
        "model_name": ANALYSIS_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "observed_facts": observed_facts,
        "potential_root_causes": hypotheses,
        "missing_information": _dedupe(missing_information),
        "potentially_relevant_authorities": (
            [payload.department_name] if payload.department_name else []
        ),
        "recommended_actions": _dedupe_actions(actions),
        "limitations": _dedupe(limitations),
        "human_verification_required": True,
        "approved_action_categories": APPROVED_ACTION_CATEGORIES,
    }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _dedupe_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for action in actions:
        key = action["action"]
        if key in seen:
            continue
        seen.add(key)
        output.append(action)
    return output
