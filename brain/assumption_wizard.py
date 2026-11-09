"""Create bounded, player-authorized provisional assumptions.

The Assumption Wizard is a resolution support process, not a normal leaf
specialist. It may fill one missing mechanism or starting value for the current
resolution, but it cannot create permanent canon or silently change rules.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

try:
    from brain.model_gateway import ModelGateway
except ModuleNotFoundError:  # Direct execution
    from model_gateway import ModelGateway


ASSUMPTION_PROMPT = """You are the Assumption Wizard for a tabletop campaign.

The player has explicitly authorized the game to decide one unresolved startup
value or missing mechanism. Create one conservative, bounded provisional
assumption only for this resolution. Do not create permanent canon, grant a new
ability, override a rule, or invent unsupported character history.

Use the supplied specialist findings and player context. Prefer established
rules, real-world baselines, existing tier bands, and the nearest comparable
mechanic. State uncertainty instead of hiding it.

Return JSON only:
{
  "status": "provisional|blocked",
  "assumption_type": "provisional_rule|initialization_seed|reward_seed",
  "name": "short identifier",
  "statement": "the assumption in plain language",
  "procedure": "how the Lead Resolver should apply it now",
  "default_value": null,
  "scope": "current_turn|current_entity|current_session",
  "basis": [],
  "limitations": [],
  "confidence": "low|medium|high",
  "persistence": "temporary_memory",
  "review_trigger": "what would justify a permanent rule or revision"
}

If the gap is actually a player fact, intent choice, or contradiction that cannot
be safely assumed, return status blocked and explain the reason in limitations.
"""


_PERMISSION_PATTERNS = (
    r"\byou decide\b",
    r"\byour choice\b",
    r"\buse your judgment\b",
    r"\buse your judgement\b",
    r"\bmake an assumption\b",
    r"\bchoose for me\b",
    r"\bmake the call\b",
    r"\bdo what makes sense\b",
)
_GAP_TERMS = (
    "no rule", "no mechanism", "not defined", "undefined", "not specified",
    "missing mechanism", "missing rule", "unknown starting", "starting value",
    "initial value", "cannot determine", "can't determine", "not established",
    "how much", "how many", "what damage",
)


class AssumptionWizard:
    """Player-authorized provisional assumption creator."""

    def __init__(self, repo_root: str | Path = "."):
        self.root = Path(repo_root).resolve()

    @classmethod
    def permission_granted(cls, answers: Any) -> bool:
        if not isinstance(answers, list):
            return False
        text = "\n".join(str(item) for item in answers if isinstance(item, str)).casefold()
        return any(re.search(pattern, text) for pattern in _PERMISSION_PATTERNS)

    @classmethod
    def gap_request(cls, context: dict[str, Any], specialist_output: dict[str, Any]) -> str | None:
        pending = context.get("pending_clarification") or context.get("previous_clarification")
        values: list[str] = []
        if isinstance(pending, dict):
            values.extend(str(pending.get(key, "")) for key in ("question", "player_question", "issue", "why"))
        for result in specialist_output.get("specialist_results", []) if isinstance(specialist_output, dict) else []:
            if not isinstance(result, dict):
                continue
            values.extend(str(result.get(key, "")) for key in ("findings", "conflicts", "evidence_requests"))
        text = " ".join(values).strip()
        if not text:
            return None
        lowered = text.casefold()
        if any(term in lowered for term in _GAP_TERMS) or re.search(r"\bno\b.{0,80}\b(rule|mechanism|definition)\b", lowered):
            return text[:2000]
        return None

    def maybe_create(self, context: dict[str, Any], specialist_output: dict[str, Any]) -> dict[str, Any] | None:
        if not self.permission_granted(context.get("answers")):
            return None
        gap = self.gap_request(context, specialist_output)
        if not gap:
            return None
        return self.create(context, specialist_output, gap)

    def create(self, context: dict[str, Any], specialist_output: dict[str, Any], gap: str) -> dict[str, Any]:
        payload = {
            "player_authorization": "The player explicitly delegated this unresolved choice.",
            "gap": gap,
            "player_input": str(context.get("message", ""))[:2000],
            "answers": [str(item) for item in context.get("answers", [])[-3:] if isinstance(item, str)],
            "position": context.get("position", {}),
            "main_character": context.get("main_character"),
            "action_frames": specialist_output.get("action_frames", []),
            "specialist_findings": self._compact_findings(specialist_output),
            "permission_scope": "current resolution only",
        }
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY")
        if not api_key:
            return self._blocked("The Assumption Wizard requires a configured model provider.")
        result = ModelGateway(self.root).complete(
            stage="assumption.wizard",
            request_id=str(context.get("turn_id", "")) or None,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            json_mode=True,
            messages=[
                {"role": "system", "content": ASSUMPTION_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        ).content
        try:
            value = json.loads(result)
        except json.JSONDecodeError:
            return self._blocked("The Assumption Wizard returned invalid structured output.")
        return self.validate(value)

    @staticmethod
    def _compact_findings(value: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for item in value.get("specialist_results", []) if isinstance(value, dict) else []:
            if not isinstance(item, dict):
                continue
            findings.append({
                "specialist": item.get("specialist"),
                "status": item.get("status"),
                "findings": item.get("findings", [])[:8] if isinstance(item.get("findings"), list) else [],
                "conflicts": item.get("conflicts", [])[:4] if isinstance(item.get("conflicts"), list) else [],
                "evidence_requests": item.get("evidence_requests", [])[:4] if isinstance(item.get("evidence_requests"), list) else [],
                "recommendation": item.get("recommendation"),
            })
        return findings

    @classmethod
    def validate(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return cls._blocked("The assumption was not an object.")
        status = value.get("status")
        if status not in {"provisional", "blocked"}:
            return cls._blocked("The assumption has an invalid status.")
        if status == "blocked":
            return {
                "status": "blocked",
                "assumption_type": value.get("assumption_type"),
                "limitations": [str(item) for item in value.get("limitations", []) if str(item)],
                "persistence": "temporary_memory",
            }
        required = ("assumption_type", "name", "statement", "procedure", "scope", "basis", "limitations", "review_trigger")
        if any(not value.get(field) for field in required):
            return cls._blocked("The provisional assumption omitted a required boundary or basis.")
        if value.get("assumption_type") not in {"provisional_rule", "initialization_seed", "reward_seed"}:
            return cls._blocked("The assumption type is not supported.")
        if value.get("scope") not in {"current_turn", "current_entity", "current_session"}:
            return cls._blocked("The assumption scope is too broad.")
        return {
            "status": "provisional",
            "assumption_type": str(value["assumption_type"]),
            "name": str(value["name"]).strip()[:120],
            "statement": str(value["statement"]).strip()[:1200],
            "procedure": str(value["procedure"]).strip()[:1600],
            "default_value": value.get("default_value"),
            "scope": str(value["scope"]),
            "basis": [str(item) for item in value.get("basis", []) if str(item)][:8],
            "limitations": [str(item) for item in value.get("limitations", []) if str(item)][:8],
            "confidence": str(value.get("confidence", "low")),
            "persistence": "temporary_memory",
            "review_trigger": str(value["review_trigger"]).strip()[:800],
            "player_authorized": True,
        }

    @staticmethod
    def _blocked(reason: str) -> dict[str, Any]:
        return {
            "status": "blocked",
            "assumption_type": None,
            "limitations": [reason],
            "persistence": "temporary_memory",
            "player_authorized": True,
        }
