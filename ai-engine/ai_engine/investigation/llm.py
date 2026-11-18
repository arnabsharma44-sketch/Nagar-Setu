"""Optional LLM investigation assistant.

The provider is behind an interface and disabled unless ``LLM_PROVIDER=openai`` and
an API key is configured. Model output is treated as untrusted text: it is parsed
into a fixed schema, unknown fields are dropped, and any failure falls back to the
deterministic draft so the workflow never depends on the provider.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger("roadguard.llm")

SYSTEM_PROMPT = (
    "You are an assistant for a municipal road-safety investigation workflow. "
    "Use only the structured records supplied in the user message. You must not "
    "declare legal liability, fault, negligence or contractual breach. You must not "
    "identify people or vehicles. You must not invent record ids, coordinates, "
    "contracts, statistics or confidence values. Label every hypothesis as unverified, "
    "and state what evidence is missing. Respond with JSON only, matching the schema."
)

RESPONSE_SCHEMA_HINT = {
    "observed_facts": ["string"],
    "potential_root_causes": [
        {
            "hypothesis": "string",
            "supporting_record_ids": ["string"],
            "counter_evidence": ["string"],
            "confidence_label": "low|medium|high",
        }
    ],
    "missing_information": ["string"],
    "potentially_relevant_authorities": ["string"],
    "recommended_actions": [
        {
            "action": "string",
            "rationale": "string",
            "priority": "low|medium|high",
            "requires_human_approval": True,
        }
    ],
    "limitations": ["string"],
}


class LlmUnavailable(RuntimeError):
    """Raised when the provider is not configured or fails."""


class LlmProvider(Protocol):
    name: str

    def complete_json(self, *, system: str, user: str, schema_hint: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class OpenAiProvider:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 30
    name: str = "openai"

    def complete_json(self, *, system: str, user: str, schema_hint: dict[str, Any]) -> dict[str, Any]:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise LlmUnavailable("The HTTP client required for the LLM provider is unavailable.") from exc

        payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"schema": schema_hint, "records": json.loads(user)}, ensure_ascii=False
                    ),
                },
            ],
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except Exception as exc:
            raise LlmUnavailable(f"LLM provider request failed: {type(exc).__name__}") from exc

        content = body.get("choices", [{}])[0].get("message", {}).get("content")
        if not content:
            raise LlmUnavailable("LLM provider returned an empty response.")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LlmUnavailable("LLM provider returned invalid JSON.") from exc


def sanitize_analysis(raw: dict[str, Any], *, model_name: str) -> dict[str, Any]:
    """Coerce untrusted model output into the fixed response shape."""

    def strings(value: Any, limit: int = 20) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item)[:1000] for item in value[:limit] if isinstance(item, (str, int, float))]

    hypotheses: list[dict[str, Any]] = []
    for item in raw.get("potential_root_causes", [])[:10] if isinstance(raw.get("potential_root_causes"), list) else []:
        if not isinstance(item, dict):
            continue
        confidence = str(item.get("confidence_label", "low")).lower()
        hypotheses.append(
            {
                "hypothesis": str(item.get("hypothesis", ""))[:1500],
                "supporting_record_ids": strings(item.get("supporting_record_ids")),
                "counter_evidence": strings(item.get("counter_evidence")),
                "confidence_label": confidence if confidence in {"low", "medium", "high"} else "low",
            }
        )

    actions: list[dict[str, Any]] = []
    for item in raw.get("recommended_actions", [])[:10] if isinstance(raw.get("recommended_actions"), list) else []:
        if not isinstance(item, dict):
            continue
        priority = str(item.get("priority", "medium")).lower()
        actions.append(
            {
                "action": str(item.get("action", ""))[:1000],
                "rationale": str(item.get("rationale", ""))[:1000],
                "priority": priority if priority in {"low", "medium", "high"} else "medium",
                "requires_human_approval": True,
            }
        )

    return {
        "observed_facts": strings(raw.get("observed_facts")),
        "potential_root_causes": hypotheses,
        "missing_information": strings(raw.get("missing_information")),
        "potentially_relevant_authorities": strings(raw.get("potentially_relevant_authorities")),
        "recommended_actions": actions,
        "limitations": strings(raw.get("limitations")),
        "human_verification_required": True,
        "model_name": model_name,
    }


def build_provider(*, provider: str, api_key: str, model: str, base_url: str, timeout: int) -> LlmProvider | None:
    if provider == "openai" and api_key and model:
        return OpenAiProvider(api_key=api_key, model=model, base_url=base_url, timeout_seconds=timeout)
    return None
