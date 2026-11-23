"""Conversational, evidence-backed admin agent.

This agent answers out-of-roleplay questions and prepares proposals. It never
writes campaign files. Approved proposals are handled by admin_editor.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from brain.state.model_gateway import ModelGateway
from brain.specialists.runner import SpecialistRunner
from admin_contracts import AdminResponse, READ_ONLY_CAMPAIGN_FILES
from approval import bind_source_versions
from brain.runtime_commands import ADMIN_AGENT_COMMANDS, normalize_agent_command


ADMIN_PROMPT = """You are the Administrative AI for an evidence-backed tabletop game.
This is an out-of-roleplay conversation with the player. Do not narrate scenes,
write dialogue, resolve a new roleplay turn, or invent facts.

Use only the frozen Evidence Bundle and specialist findings. Distinguish:
established fact, player claim, rule, interpretation, contradiction, and unknown.
If the player claims a record is wrong, investigate it against the evidence before
agreeing. If a file change is appropriate, prepare an exact proposal but never
apply it yourself.

Return JSON only:
{
  "status": "answered|proposal_ready|needs_clarification|blocked",
  "answer": "clear out-of-roleplay answer",
  "diagnosis": {
    "issue": "what was decided or what is blocking the result",
    "why": "brief evidence-backed reason for the result",
    "internal_search": true,
    "evidence_request": "what the Evidence Bundle should search next, or empty",
    "specialists": ["appropriate specialist names"],
    "player_question": "only when internal evidence cannot resolve the issue"
  },
  "evidence": [{"source": "...", "location": "...", "claim": "..."}],
  "changes": [{
    "target_file": "markdown_files/...md or outside game/templates/...md",
    "action": "create|fill|update|delete",
    "template": "registered template name when creating or filling",
    "values": {"field": "approved value"},
    "old_text": "exact existing text or empty for create",
    "new_text": "exact replacement or empty for delete",
    "reason": "evidence-backed reason"
  }],
  "instructions": [{"target": "brain|backend", "instruction": "...", "reason": "..."}],
  "questions": [],
  "conflicts": [],
  "runtime_command": null,
  "approval_required": false
}

The rules file `markdown_files/game rules (1).md` is read-only evidence. Never
propose, apply, or include a change targeting it; if a request asks to edit it,
return blocked and explain that rules changes must be made manually by the
player outside this AI workflow.

Only use proposal_ready when an exact change is supported. Use registered
Markdown templates for document creation and filling. Store final campaign
content as readable Markdown, never as JSON blobs. A number change should be an
exact line update when possible; update an existing description or section
instead of appending a duplicate section. Code instructions are plans only and
are never file edits. A write proposal must set approval_required true. You may request one safe runtime command in `runtime_command` when the player explicitly asked for an operational action. Use the slash command name and optional argument. Supported requests are `/status`, `/retry`, `/pause`, `/resume`, `/review`, `/next-file`, `/back-setup`, `/undo`, `/undo-setup`, `/cancel-operation`, `/end-day`, `/specialists`, `/new-character`, `/new-party-member`, `/add`, and `/install`. You must never request `/new-game`, `/cancel-setup`, `/approve`, `/approve-reset`, `/main`, or `/quit`; those remain player-controlled or approval-gated. Keep modifier types distinct
in every proposal: Stat Modifiers are stat-specific
expressions, Effect Modifiers are action/technique-specific, and Class Modifiers
are class-specific. Stat Modifiers must stay broad within the stat domain: STR is
forceful physical action rather than sword-only damage, and INT is analysis, pattern
recognition, noticing flaws, and problem solving rather than combat-only analysis.
They may all apply to one action when relevant; preserve their separate evidence,
activation conditions, and descriptions.
For Stat Modifier proposals, do not invent a no-stacking, highest-single, or
same-evidence exclusion. Sum all relevant bonuses unless a specific supplied
rule explicitly limits that combination; preserve only explicit overlap
restrictions such as Practice Carryover double-counting or a superseded facility
version. For Stat Modifier proposals, preserve three choices for every eligible Stat
Modifier slot; do not collapse several slots into three total choices. Every choice
must remain a broad stat-domain capability across multiple situations. Do not
rewrite a broad stat capability as a room-, tool-, profession-, maneuver-,
combat-exchange-, or single-task-specific technique; those belong to Effect
Modifiers. Preserve the explicit `breadth: broad_stat_domain` field and the choice's
evidence, limitations, and growth/conversion rule in readable Markdown. Label each
choice as high, low, or assumed_low basis. More independent demonstrated bases
may support a higher magnitude within the applicable tier band; no-base generic
choices must remain low or assumed_low and must not be presented as established
history. The universal magnitude bands are: Tier 0 +1 to +2, Tier 1 +2 to +5,
Tier 2 +5 to +10, Tier 3 +10 to +20, Tier 4 +20 to +50, and Tier 5 +50 to
+100. These are hard per-modifier bounds; evidence chooses within the band,
and relevant modifiers sum unless an explicit rule restricts stacking. For the starting Effect Modifier setup batch, preserve ten choices and
make clear that the player selects three. Do not silently reduce the ten choices
or auto-select effects. Each choice must be grounded in the character description
and tier, with high, low, or assumed_low basis clearly labeled. For every available
Class Modifier slot, preserve five class-specific choices and make clear that the
player selects one per slot; do not auto-select class options.
Always provide `diagnosis.issue` and `diagnosis.why`, including for answered and
proposal results. If the result is blocked or needs clarification, first describe
whether the missing information may be found internally. Set `internal_search`
true and provide a concrete `evidence_request` plus appropriate `specialists`
when another evidence round may solve it. Set `internal_search` false only when
only the player's intent, choice, or missing personal fact can resolve it. Keep
reasons concise and evidence-backed; do not expose internal chain-of-thought.

When `clarification_continuation` is present and contains an `answer`, that
answer is the player's response to the exact linked question. Validate it against
the frozen linked result and specialist findings. Do not ask the same question
again, do not regenerate the choices, and do not treat the answer as a new
unrelated request. If it selects a valid option, continue to proposal_ready (or
state the specific rule conflict); if it is invalid or ambiguous, ask only for
the missing correction.
"""


class AdminAgent:
    def __init__(self, repo_root: str | Path = "."):
        self.repo_root = Path(repo_root).resolve()

    def respond(
        self,
        bundle_record: dict[str, Any],
        *,
        specialist_output: dict[str, Any] | None = None,
        mode: str = "auto",
    ) -> dict[str, Any]:
        request = bundle_record.get("admin_request", {})
        request_id = str(bundle_record.get("turn_id", f"admin-{uuid.uuid4().hex[:8]}"))
        if mode == "dummy":
            return self._dummy_response(bundle_record, request_id)
        if specialist_output is None:
            if mode == "auto" and not self._api_key():
                specialist_output = {
                    "specialist_results": [],
                    "coverage": {"required": [], "note": "Specialists were unavailable without an API key."},
                }
            else:
                specialist_output = self._specialists(bundle_record, mode=mode)
        if not self._api_key():
            return {
                "request_id": request_id,
                "status": "blocked",
                "answer": "The Administrative AI requires DEEPSEEK_API_KEY or API_KEY.",
                "diagnosis": {
                    "issue": "Administrative AI provider credentials are unavailable.",
                    "why": "No configured provider key is available to produce an evidence-backed administrative result.",
                    "internal_search": False,
                    "evidence_request": "",
                    "specialists": [],
                    "player_question": "Administrative AI credentials must be configured before this request can be completed.",
                },
                "evidence": [],
                "changes": [],
                "instructions": [],
                "questions": [],
                "conflicts": [],
                "approval_required": False,
                "specialist_output": specialist_output,
            }
        evidence_bundle = bundle_record.get("evidence_bundle", bundle_record)
        current_state = evidence_bundle.get("current_state", {}) if isinstance(evidence_bundle, dict) else {}
        clarification = current_state.get("active_clarification") if isinstance(current_state, dict) else None
        payload = {
            "admin_request": request,
            "player_input": bundle_record.get("player_input", {}),
            "clarification_continuation": clarification if isinstance(clarification, dict) else None,
            "selected_sections": evidence_bundle.get("selected_sections", []),
            "admin_sources": evidence_bundle.get("admin_sources", []),
            "evidence_gaps": evidence_bundle.get("evidence_gaps", []),
            "specialist_results": specialist_output.get("specialist_results", []),
            "coverage": specialist_output.get("coverage", {}),
        }
        raw = ModelGateway(self.repo_root).complete(
            stage="admin.response",
            request_id=request_id,
            model=os.getenv("ADMIN_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-chat")),
            json_mode=True,
            timeout=180,
            messages=[
                {"role": "system", "content": ADMIN_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        ).content
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Administrative AI returned invalid JSON") from exc
        result = self._validate(result, request_id)
        result["proposed_by"] = "admin_agent"
        if result.get("status") == "proposal_ready" and isinstance(result.get("changes"), list):
            result = bind_source_versions(result, repo_root=self.repo_root)
        result["specialist_output"] = specialist_output
        return result

    def prepare_document_proposal(
        self,
        *,
        request_id: str,
        changes: list[dict[str, Any]],
        answer: str,
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a deterministic Admin Agent proposal for approved documentation.

        This keeps non-roleplay documentation on the same Admin Agent → approval
        → Admin Editor path without requiring a second model call for text the
        player has already explicitly approved.
        """
        value = self._validate({
            "status": "proposal_ready",
            "answer": answer,
            "evidence": evidence or [],
            "changes": changes,
            "instructions": [],
            "questions": [],
            "conflicts": [],
            "modifier_group_placements": [],
            "approval_required": True,
        }, request_id)
        value["proposed_by"] = "admin_agent"
        return bind_source_versions(value, repo_root=self.repo_root)

    def _specialists(self, bundle_record: dict[str, Any], *, mode: str) -> dict[str, Any]:
        if mode == "no_specialists":
            return {"specialist_results": [], "coverage": {"required": []}}
        names = bundle_record.get("required_specialists", [])
        if not isinstance(names, list):
            names = []
        return SpecialistRunner(self.repo_root).run(bundle_record, names)

    @staticmethod
    def _validate(value: Any, request_id: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise RuntimeError("Administrative AI response must be an object")
        status = value.get("status")
        if status not in {"answered", "proposal_ready", "needs_clarification", "blocked"}:
            raise RuntimeError("Administrative AI returned an invalid status")
        for field in ("evidence", "changes", "instructions", "questions", "conflicts", "modifier_group_placements"):
            if not isinstance(value.get(field, []), list):
                raise RuntimeError(f"Administrative AI field must be a list: {field}")
        raw_diagnosis = value.get("diagnosis")
        if not isinstance(raw_diagnosis, dict):
            raw_diagnosis = {}
        diagnosis = {
            "issue": str(raw_diagnosis.get("issue") or (value.get("questions") or value.get("answer") or "No administrative issue reported.")),
            "why": str(raw_diagnosis.get("why") or "The result was produced from the frozen evidence and specialist findings."),
            "internal_search": bool(raw_diagnosis.get("internal_search", False)),
            "evidence_request": str(raw_diagnosis.get("evidence_request") or ""),
            "specialists": [str(item) for item in raw_diagnosis.get("specialists", []) if isinstance(item, str)],
            "player_question": str(raw_diagnosis.get("player_question") or ""),
        }
        placements = []
        placement_fields = (
            "character", "modifier", "group", "decision", "use_in_group",
            "activation_conditions", "limitations", "admin_defense", "evidence",
            "stacking", "admin_rationale",
        )
        for placement in value.get("modifier_group_placements", []):
            if not isinstance(placement, dict):
                continue
            if any(not placement.get(field) for field in placement_fields):
                continue
            if placement.get("decision") not in {"approved", "rejected", "needs_review"}:
                continue
            placements.append(placement)
        changes = []
        for change in value.get("changes", []):
            if not isinstance(change, dict):
                continue
            if change.get("action") not in {"create", "fill", "update", "delete"}:
                continue
            if not isinstance(change.get("target_file"), str):
                continue
            changes.append(change)
        def has_modifier_group_placement(text: str) -> bool:
            """Detect an actual placement, not an empty template heading."""
            match = re.search(r'^###\s+Modifier Groups\s*$', text, re.IGNORECASE | re.MULTILINE)
            if not match:
                return False
            section = text[match.end():]
            next_section = re.search(r'^##\s+', section, re.MULTILINE)
            if next_section:
                section = section[:next_section.start()]
            if 'admin defense' in section.casefold():
                return True
            return bool(re.search(r'^####\s+\S|^\s*[-*]\s+character\s*:', section, re.IGNORECASE | re.MULTILINE))

        def has_modifier_group_values(values: Any) -> bool:
            """Return true only for actual placement data, not an empty section."""
            if not isinstance(values, dict) or "modifier_groups" not in values:
                return False
            candidate = values.get("modifier_groups")
            if isinstance(candidate, list):
                return any(
                    isinstance(item, dict)
                    and all(item.get(field) for field in ("character", "modifier", "group"))
                    for item in candidate
                )
            if isinstance(candidate, dict):
                return all(candidate.get(field) for field in ("character", "modifier", "group"))
            text = str(candidate)
            return bool(re.search(
                r"(?:^|\\b)(?:character|modifier|group|admin\\s+defense)\\s*:",
                text,
                re.IGNORECASE | re.MULTILINE,
            ))

        modifier_group_change = any(
            "status sheet.md" in str(change.get("target_file", "")).casefold()
            and (
                has_modifier_group_placement(str(change.get("new_text", "")))
                or has_modifier_group_values(change.get("values"))
            )
            for change in changes
        )
        read_only_targets = sorted({
            str(change.get('target_file')) for change in changes
            if str(change.get('target_file')) in READ_ONLY_CAMPAIGN_FILES
        })
        read_only_conflicts = [
            {
                'type': 'read_only_target',
                'target_file': target,
                'reason': 'The rules file is read-only and cannot be edited by the AI.',
            }
            for target in read_only_targets
        ]
        if read_only_targets:
            changes = []
            status = 'blocked'
        conflicts = [item for item in value.get("conflicts", []) if isinstance(item, dict)] + read_only_conflicts
        defense_in_markdown = all(
            "admin defense" in str(change.get("new_text", "")).casefold()
            for change in changes
            if "status sheet.md" in str(change.get("target_file", "")).casefold()
        )
        try:
            runtime_command = normalize_agent_command(value.get("runtime_command"), allowed=ADMIN_AGENT_COMMANDS)
        except ValueError as exc:
            status = "blocked"
            conflicts = [*conflicts, {"type": "protected_runtime_command", "reason": str(exc)}]
            runtime_command = None
        if modifier_group_change and (
            not placements
            or not defense_in_markdown
            or any(item.get("decision") != "approved" for item in placements)
        ):
            status = "needs_clarification"
            conflicts.append({
                "type": "modifier_group_defense_missing",
                "reason": "Every Modifier Group placement must be individually defended and approved before it can be written.",
            })
        if changes and status not in {"proposal_ready", "needs_clarification"}:
            status = "proposal_ready"
        return {
            "request_id": request_id,
            "status": status,
            "answer": str(value.get("answer", "")),
            "diagnosis": diagnosis,
            "evidence": [item for item in value.get("evidence", []) if isinstance(item, dict)],
            "changes": changes,
            "instructions": [item for item in value.get("instructions", []) if isinstance(item, dict)],
            "questions": [item for item in value.get("questions", []) if isinstance(item, str)],
            "conflicts": conflicts,
            "modifier_group_placements": placements,
            "runtime_command": runtime_command,
            "approval_required": bool(value.get("approval_required", bool(changes))),
        }

    @staticmethod
    def _dummy_response(bundle_record: dict[str, Any], request_id: str) -> dict[str, Any]:
        request = bundle_record.get("admin_request", {})
        operation = request.get("operation", "question") if isinstance(request, dict) else "question"
        target = request.get("target", "game_state") if isinstance(request, dict) else "game_state"
        return AdminResponse(
            request_id=request_id,
            status="answered",
            answer=f"Dummy admin answer for {operation} about {target}. Evidence was frozen before analysis.",
            diagnosis={
                "issue": "The administrative request was answered in dummy mode.",
                "why": "The request was routed outside roleplay and the evidence bundle was frozen first.",
                "internal_search": False,
                "evidence_request": "",
                "specialists": [],
                "player_question": "",
            },
            evidence=[{"source": "admin_request", "location": "request", "claim": "The request was received outside roleplay."}],
        ).to_dict()

    def _api_key(self) -> str | None:
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=self.repo_root / ".env")
        except ImportError:
            pass
        return os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY")


def main() -> None:
    parser = argparse.ArgumentParser(description="Answer an evidence-backed outside-game request")
    parser.add_argument("bundle", help="Routing/evidence bundle JSON file or '-'")
    parser.add_argument("--mode", choices=("auto", "no_specialists", "dummy"), default="auto")
    args = parser.parse_args()
    raw = sys.stdin.read() if args.bundle == "-" else Path(args.bundle).read_text(encoding="utf-8")
    data = json.loads(raw)
    result = AdminAgent(Path(__file__).resolve().parents[1]).respond(data, mode=args.mode)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
