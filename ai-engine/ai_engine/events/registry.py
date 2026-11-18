"""Versioned event-rule registry.

Rules run in a fixed order so stronger evidence wins: a collision candidate
suppresses a near-miss candidate for the same track pair.
"""

from __future__ import annotations

from typing import Any

from ai_engine.events import (
    collision,
    near_miss,
    pedestrian_conflict,
    rapid_motion,
    signal_violation,
    wrong_way,
)
from ai_engine.events.base import CandidateEvent, RuleConfig, RuleOutcome
from ai_engine.tracking.tracker import Track

MAX_EVENTS_PER_JOB = 10


def evaluate_all(
    tracks: list[Track], config: RuleConfig, scene_config: dict[str, Any] | None = None
) -> tuple[list[CandidateEvent], list[RuleOutcome]]:
    outcomes: list[RuleOutcome] = []

    collision_events = collision.evaluate(tracks, config)
    outcomes.append(
        RuleOutcome(
            name=collision.RULE_NAME,
            version=collision.RULE_VERSION,
            status="evaluated",
            events=collision_events,
        )
    )

    near_miss_events = near_miss.evaluate(
        tracks, config, excluded_pairs=collision.pairs_used(collision_events)
    )
    outcomes.append(
        RuleOutcome(
            name=near_miss.RULE_NAME,
            version=near_miss.RULE_VERSION,
            status="evaluated",
            events=near_miss_events,
        )
    )

    pedestrian_events = pedestrian_conflict.evaluate(tracks, config)
    outcomes.append(
        RuleOutcome(
            name=pedestrian_conflict.RULE_NAME,
            version=pedestrian_conflict.RULE_VERSION,
            status="evaluated",
            events=pedestrian_events,
        )
    )

    rapid_events = rapid_motion.evaluate(tracks, config)
    outcomes.append(
        RuleOutcome(
            name=rapid_motion.RULE_NAME,
            version=rapid_motion.RULE_VERSION,
            status="evaluated",
            events=rapid_events,
        )
    )

    outcomes.append(wrong_way.evaluate(tracks, config, scene_config))
    outcomes.append(signal_violation.evaluate(tracks, config, scene_config))

    events: list[CandidateEvent] = []
    seen: set[tuple[str, tuple[int, ...]]] = set()
    for outcome in outcomes:
        for event in outcome.events:
            key = (event.event_type, tuple(sorted(event.track_ids)))
            if key in seen:
                continue
            seen.add(key)
            events.append(event)

    events.sort(key=lambda event: event.score, reverse=True)
    return events[:MAX_EVENTS_PER_JOB], outcomes


def rule_manifest() -> list[dict[str, str]]:
    return [
        {"name": near_miss.RULE_NAME, "version": near_miss.RULE_VERSION, "status": "evaluated"},
        {"name": collision.RULE_NAME, "version": collision.RULE_VERSION, "status": "evaluated"},
        {
            "name": pedestrian_conflict.RULE_NAME,
            "version": pedestrian_conflict.RULE_VERSION,
            "status": "evaluated",
        },
        {"name": rapid_motion.RULE_NAME, "version": rapid_motion.RULE_VERSION, "status": "evaluated"},
        {"name": wrong_way.RULE_NAME, "version": wrong_way.RULE_VERSION, "status": "conditional"},
        {
            "name": signal_violation.RULE_NAME,
            "version": signal_violation.RULE_VERSION,
            "status": "unavailable",
        },
    ]
