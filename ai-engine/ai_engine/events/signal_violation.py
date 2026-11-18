"""E-04 signal-line crossing candidate — reported as unavailable.

Evaluating this rule requires a synchronised signal state, a configured stop line
and camera geometry that this prototype does not have. Guessing signal state from
pixel colours is explicitly out of scope, so the rule is registered and marked
unavailable instead of producing unsupported events.
"""

from __future__ import annotations

from ai_engine.events.base import CandidateEvent, RuleConfig, RuleOutcome
from ai_engine.tracking.tracker import Track

RULE_NAME = "signal_line_crossing_v1"
RULE_VERSION = "1.0.0"

UNAVAILABLE_NOTE = (
    "No synchronised signal state or configured stop line is available for this "
    "camera. Signal state is never inferred from pixel colour alone."
)


def evaluate(tracks: list[Track], config: RuleConfig, scene_config: dict | None) -> RuleOutcome:
    if not (scene_config or {}).get("signal_state_feed"):
        return RuleOutcome(
            name=RULE_NAME, version=RULE_VERSION, status="unavailable", note=UNAVAILABLE_NOTE
        )
    return RuleOutcome(
        name=RULE_NAME,
        version=RULE_VERSION,
        status="unavailable",
        note="A signal-state feed is configured but the validator is not implemented in this build.",
    )


__all__ = ["CandidateEvent", "evaluate", "RULE_NAME", "RULE_VERSION"]
