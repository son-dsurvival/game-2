"""Adjudicate Evidence Bundle gaps before Lead Resolver analysis."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from brain.model_gateway import ModelGateway
except ModuleNotFoundError:  # Direct execution from brain/specialists.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from brain.model_gateway import ModelGateway


HARD_GAP_TYPES = {
    "malformed_sections",
    "malformed_section",
    "invalid_section_reference",
    "invalid_line_range",
    "stale_index",
    "missing_index_source",
}
ENTITY_GAP_TYPES = {"missing_entity_evidence", "missing_entity_heading", "entity_mismatch"}
DECISIONS = {"proceed", "expand_evidence", "clarify", "block"}

ADJUDICATOR_PROMPT = """You are the Evidence Gap Adjudicator for a game runtime.

Decide whether the available indexed evidence is sufficient for specialists and
the Lead Resolver to continue. You receive action frames, routed tags, selected
section descriptions, and evidence gaps. You do not read campaign files and you
must not invent facts.

Judge each gap by its effect on this specific turn. A gap is material only if it
could change action validity, a required cost, time, NPC reaction, progression
eligibility, current-state availability, or an important consequence. Missing
aliases, duplicate requests, unrelated headings, and optional background are
minor or irrelevant when the selected sections already answer the turn's
specialist questions. Do not request expansion merely because a gap exists.
Proceed when the remaining gaps cannot affect this turn's analysis.

Return JSON only:
{
  "decision": "proceed|expand_evidence|clarify|block",
  "gap_assessments": [
    {"gap_index": 0, "severity": "blocking|non_blocking|needs_expansion", "impact": "material|minor|irrelevant", "reason": "..."}
  ],
  "evidence_requests": [
    {"request": "what indexed evidence to search for", "reason": "..."}
  ],
  "clarification_questions": [],
  "note": "short explanation for the next stage"
}

Rules:
- Never approve a missing named-entity section as if another entity were equivalent.
- Use expand_evidence only when a material gap is likely answerable by another indexed section.
- Use clarify when the player must define an entity, target, method, or intent.
- Use block when required evidence is absent, malformed, stale, or unsafe to infer.
- Use proceed when the remaining gaps are minor or irrelevant to this turn.
- Evidence requests are search requests, not invented evidence.
- A rest action should not be blocked by unrelated XP or experiment-history gaps.
- A training action should not be blocked by unrelated relationship or world-history gaps.
"""


class GapAdjudicator:
    def __init__(self, repo_root: str | Path = "."):
        self.repo_root = Path(repo_root).resolve()

    def adjudicate(
        self,
        bundle_record: dict[str, Any],
        *,
        mode: str = "auto",
    ) -> dict[str, Any]:
        bundle = bundle_record.get("evidence_bundle", bundle_record)
        gaps = bundle.get("evidence_gaps", [])
        if not isinstance(gaps, list):
            gaps = []
        gaps = [gap for gap in gaps if isinstance(gap, dict)]
        if not gaps:
            return self._result(
                "proceed", [], [], [], "No evidence gaps were reported."
            )

        hard = [
            (index, gap)
            for index, gap in enumerate(gaps)
            if gap.get("type") in HARD_GAP_TYPES
        ]
        if mode == "heuristic" or (mode == "auto" and not self._api_key()):
            if hard:
                return self._result(
                    "block",
                    self._assessments(gaps, hard),
                    [],
                    [],
                    "Hard evidence integrity gaps require correction before resolution.",
                )
            return self._result(
                "expand_evidence",
                self._assessments(gaps, []),
                [{"request": self._gap_request(gap), "reason": "Evidence gap requires another indexed search."} for gap in gaps],
                [],
                "Additional indexed evidence should be searched before resolution.",
            )
        if not self._api_key():
            raise RuntimeError("Gap adjudication requires DEEPSEEK_API_KEY or API_KEY")

        payload = {
            "player_input": bundle.get("player_input", {}),
            "action_frames": bundle.get("action_frames", []),
            "selected_sections": bundle.get("selected_sections", []),
            "evidence_gaps": gaps,
            "routing_record": {
                "mode": bundle_record.get("mode"),
                "tags": bundle_record.get("tags", []),
                "required_specialists": bundle_record.get("required_specialists", []),
            },
        }
        content = ModelGateway(self.repo_root).complete(
            stage="evidence.gap_adjudication",
            request_id=str(bundle_record.get("turn_id", "")) or None,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            json_mode=True,
            messages=[
                {"role": "system", "content": ADJUDICATOR_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        ).content
        if not content:
            raise RuntimeError("DeepSeek returned an empty gap-adjudication response")
        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("DeepSeek returned invalid gap-adjudication JSON") from exc
        return self._validate(result, gaps, hard)

    def _validate(
        self,
        result: Any,
        gaps: list[dict[str, Any]],
        hard: list[tuple[int, dict[str, Any]]],
    ) -> dict[str, Any]:
        if not isinstance(result, dict) or result.get("decision") not in DECISIONS:
            raise RuntimeError("Gap adjudicator returned an invalid decision")
        decision = result["decision"]
        assessments = result.get("gap_assessments", [])
        requests = result.get("evidence_requests", [])
        questions = result.get("clarification_questions", [])
        if not isinstance(assessments, list) or not isinstance(requests, list) or not isinstance(questions, list):
            raise RuntimeError("Gap adjudicator returned malformed lists")
        assessments = [item for item in assessments if isinstance(item, dict)]
        requests = [
            item for item in requests
            if isinstance(item, dict)
            and isinstance(item.get("request"), str)
            and isinstance(item.get("reason"), str)
        ]
        questions = [item for item in questions if isinstance(item, str)]
        if hard and decision == "proceed":
            decision = "block"
            note = "The model proposed proceeding, but Python enforced hard evidence-integrity gaps."
        else:
            note = str(result.get("note", "")).strip()
        if decision == "expand_evidence" and not requests:
            requests = [{"request": self._gap_request(gap), "reason": "Unresolved evidence gap."} for gap in gaps]
        return self._result(decision, assessments, requests, questions, note)

    @staticmethod
    def _result(
        decision: str,
        assessments: list[dict[str, Any]],
        requests: list[dict[str, Any]],
        questions: list[str],
        note: str,
    ) -> dict[str, Any]:
        return {
            "decision": decision,
            "gap_assessments": assessments,
            "evidence_requests": requests,
            "clarification_questions": questions,
            "note": note,
        }

    @staticmethod
    def _assessments(
        gaps: list[dict[str, Any]], hard: list[tuple[int, dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        hard_indices = {index for index, _ in hard}
        return [
            {
                "gap_index": index,
                "severity": "blocking" if index in hard_indices else "needs_expansion",
                "reason": "Hard evidence integrity gap." if index in hard_indices else "Additional indexed evidence may resolve this gap.",
            }
            for index, _ in enumerate(gaps)
        ]

    @staticmethod
    def _gap_request(gap: dict[str, Any]) -> str:
        return str(
            gap.get("request")
            or gap.get("heading")
            or gap.get("entity")
            or gap.get("source")
            or "unresolved evidence"
        )

    @staticmethod
    def _api_key() -> str | None:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        return os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY")


def _load_json(argument: str) -> dict[str, Any]:
    raw = sys.stdin.read() if argument == "-" else Path(argument).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SystemExit("Gap Adjudicator input must be a JSON object")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Adjudicate Evidence Bundle gaps")
    parser.add_argument("bundle", help="Evidence Bundle JSON file or '-' for stdin")
    parser.add_argument("--mode", choices=("auto", "deepseek", "heuristic"), default="auto")
    args = parser.parse_args()
    result = GapAdjudicator().adjudicate(_load_json(args.bundle), mode=args.mode)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
