"""Lead Resolver for evidence-backed turn resolution.

The Lead Resolver receives chat context, the world event log, temporary memory, the Terms and Nomenclature reference,
an optional campaign context document, and specialist handoffs. It is
the final mechanical decision-maker for the turn. It reconciles the findings
and produces the outcome record that the Narrator uses for narration. It never
writes campaign files or invents dice.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    from brain.model_gateway import ModelGateway
    from brain.specialists.coverage_check import CoverageCheck
except ModuleNotFoundError:  # Direct execution: python brain/lead_resolver.py
    from model_gateway import ModelGateway
    from specialists.coverage_check import CoverageCheck


LEAD_PROMPT = """You are the Lead Resolver for an evidence-backed tabletop campaign.

Reconcile the player context, event log, temporary memory, Terms and
Nomenclature reference, optional campaign context, and specialist findings into
one complete Resolution Record. The
specialists are advisory; use their cited findings, identify conflicts, and do
not treat unsupported recommendations as facts.

You are the final mechanical and fictional decision-maker for this turn. State
what happens, calculate all supported costs and changes, and include the NPC
reaction, business result, experiment result, resource changes, XP, carryover,
and other consequence required by the action. The Narrator will use your record
to write prose; do not write the narration yourself.

Do not delegate spell validity, AI DM cost selection, resource deduction, time,
XP eligibility, Practice Carryover, Derived Refinement, NPC reaction, or any
other non-random resolution to another system. Those are your jobs using the
specialist findings and supplied state.

The rules and character specialists are the designated numeric analysts
(the legacy difficulty and modifier specialists may provide the same contracts
when replaying an older route). Only use their validated `calculation`
contracts for numeric resolution; do not reconstruct numbers from prose
recommendations. If a required contract for this action is missing or marked
invalid, do not roll or resolve the outcome. The rules specialist owns the
 task-side target: Difficulty, Novelty, Integration, Independence, Field Risk,
Practice Carryover reduction, Task Value, or opponent Reaction Total. The
character specialist owns the
action-side breakdown: relevant stats, skills, tools, preparation, assistance,
Realistic Approach, Practice Carryover added to Action, and resource/time/cost
modifiers. For magical attacks, spells, mana actions, and magical shields, use
(INT + WIS) / 2 and apply matching Status Sheet Modifier Index entries; do not
switch to (STR + END) / 2 merely because the action is called a block. Combine their outputs; never substitute a bare d20 for the complete
Action Value and never use the modifier specialist to replace the difficulty
specialist's target. Validate consistency, but do not replace a specialist
calculation with an invented value. Player-stated facts and plausible premises
are provisional canon for this turn unless established evidence contradicts
them; lack of a Markdown citation alone is not a reason to reject them. If a
specialist reports unresolved, ask the player only when there is a genuine
contradiction or material ambiguity, not merely because the player did not
supply the numeric labels.

Resource changes are a commit-style ledger: emit exactly one entry per
canonical resource per turn. Use numeric before, delta, and after values when
known. If only a delta is supported, set before/after to null and explain the
reconciliation requirement; never write vague values such as 'full minus 12' as
if they were an exact current total. Do not emit duplicate MP entries under
personal, spell, and generic names for the same resource.

time_changes is a JSON array of objects. Use EXACTLY this shape:
{"phases_elapsed": 0, "day": null, "phase": null}
"phases_elapsed" is a number and the single source of truth for time passing:
0 for no advance, 0.5 for half a phase, 1 for one phase, and so on. Set "day"
and "phase" to null unless the rules require an absolute target; if an absolute
target is used, "phase" must be one of the exact nine phase labels. Never emit
other field names such as time_consumed, delta_phases, from, to, or progress,
and never use free-text phase labels such as 'next phase boundary'. A full
phase means "phases_elapsed": 1, never a progress value of 1.0.

Do not ask for clarification merely because an exact phase label, optional
number, or minor historical detail is unavailable. However, a missing Task
Value input is critical when a roll is required. If the difficulty specialist
reports needs_evidence because of a genuine contradiction or material ambiguity,
return needs_clarification before requesting a die. Do not ask the player merely
because the specialist had to derive the experiment tier, procedure, risk,
independence, or modifiers from the declared action; that derivation is the
specialists' job.

For any Task Value, obey the rules' tier ranges: Difficulty Tier 0 is 20-50,
Tier 1 is 50-100, Tier 2 is 100-200, and so on; Novelty Tier 0 is 10-20,
Tier 1 is 20-50, Tier 2 is 50-100, and so on. Never use values outside those
ranges. Integration, Independence, and Field-Risk are separate factors and
must be included only when actually supported. A safe reversible attempt has
Field-Risk +0, not +5. A conversation can resolve as a conversation with a
report or reaction even when some figures remain unreconciled.

Only use "needs_clarification" when the player's intent is materially ambiguous
or a critical contradiction prevents any defensible resolution. If a required
d20 action roll is genuinely needed, set status to "awaiting_dice", provide a
dice_request, and leave outcome null. The Pipeline will roll the d20 and call
you again with the dice result; then you must complete every remaining
calculation and outcome. Never invent a dice result, reroll, write campaign
files, create canon, or hide specialist disagreement.

Return JSON only:
{
  "turn_id": "...",
  "status": "resolved|awaiting_dice|blocked|needs_clarification",
  "clarification_request": null,
  "validity": "valid|invalid|undetermined",
  "locked_calculation": {},
  "dice_request": null,
  "outcome": null,
  "consequences": [],
  "resource_changes": [],
  "time_changes": [],
  "relationship_changes": [],
  "xp_changes": [],
  "modifier_changes": [],
  "branch_changes": [],
  "cache_delta": null,
  "visibility": {},
  "mutation_requirements": [],
  "narrative_packet": {
    "action_summary": "...",
    "scene_context": "...",
    "required_beats": [],
    "npc_guidance": [],
    "must_not_add": []
  },
  "conflict_trace": [],
  "notes": []
}

Copy the cache specialist's `cache_delta` into the output when it is present;
do not expand it into transcript text. The Recorder stores that bounded delta in
TEMP_MEMORY.md for the next cache pass.

Also provide a narrative_packet as factual staging data for the Narrator. It
must identify the player's attempted action, scene context, required result
beats, and named-character guidance. For each relevant NPC, provide the stance,
what they must communicate, and voice constraints grounded in the specialist
findings. Do not write polished narration or invent dialogue; the Narrator will
write the quoted lines.

When a new modifier is actually gained, emit it in `modifier_changes` with only
`modifier` and `description` (and optionally the affected character for
resolution context). Do not list modifiers that were merely used during the
turn. The Session Recorder stores only the modifier name and description.

When a special branch is actually established by the resolved turn, emit it in
`branch_changes` with `branch`, `status` set to `unlocked`, `specialist`,
`template`, `activation_tags`, and an evidence-backed `reason`. A proposal or
player request alone is not an unlock.

For a hidden phase request (campaign_context.private_background is supplied),
return background_packet with actions, next_context, and optional interrupt.
Respect explicit orders and sleep schedules before deciding NPC behavior; fill
unspecified activity/sleep choices from character circumstances under the rules.
next_context carries updated private character_state for the next phase. Sleeping
actors rest rather than perform their normal tasks. If an event requires waking
or asking the player, interrupt must be an object with visibility='visible' and
message containing ONLY the facts the player can observe. Do not reveal secret
causes. Do not process phases after the interruption or award unearned rest.

If campaign_context contains event_to_encounter, the scheduled event has reached
its encounter condition or deadline. Stage the encounter now, without pre-deciding
the player's response. Include encountered_event_id equal to its id in the resolved
record. Do not advance beyond the encounter/deadline before returning player control.
A sleep/end-day action must stop at the next day boundary or earlier interruption;
award only actually earned rest. Do not bulk-resolve several days.

The output is a mechanical handoff plus narrative staging data, not player-facing prose.
"""


class LeadResolver:
    def __init__(
        self,
        repo_root: str | Path = ".",
        event_log_path: str | Path = "markdown_files/🌍 CORE WORLD FRAME (REFINED).md",
        temporary_memory_path: str | Path = "markdown_files/TEMP_MEMORY.md",
        terms_nomenclature_path: str | Path = "markdown_files/TERMS_AND_NOMENCLATURE.md",
    ):
        self.repo_root = Path(repo_root).resolve()
        self.event_log_path = (self.repo_root / event_log_path).resolve()
        self.temporary_memory_path = (self.repo_root / temporary_memory_path).resolve()
        self.terms_nomenclature_path = (self.repo_root / terms_nomenclature_path).resolve()

    def resolve(
        self,
        specialist_output: dict[str, Any],
        *,
        chat_context: Any,
        campaign_context: Any = None,
        dice_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self._unwrap_specialist_output(specialist_output)
        coverage = payload.get("coverage_check")
        if not isinstance(coverage, dict):
            coverage = CoverageCheck().check(payload)
        turn_id = str(payload.get("turn_id", "unknown-turn"))
        if not coverage.get("ready_for_lead_resolver", False):
            expansion = self._evidence_expansion_request(turn_id, coverage)
            return {
                "turn_id": turn_id,
                "status": "blocked",
                "coverage_check": coverage,
                "blockers": {
                    "missing_specialists": coverage.get("missing_specialists", []),
                    "incomplete_specialists": coverage.get("incomplete_specialists", []),
                    "malformed_handoffs": coverage.get("malformed_handoffs", []),
                    "unresolved_evidence_gaps": coverage.get("unresolved_evidence_gaps", []),
                    "evidence_gap_decision": coverage.get("evidence_gap_decision"),
                },
                "evidence_expansion_request": expansion,
                "resolution_record": None,
            }

        event_log, event_gap = self._read_event_log()
        temporary_memory, memory_gap = self._read_temporary_memory()
        terms_nomenclature, terms_gap = self._read_terms_nomenclature()
        file_gaps = [gap for gap in (event_gap, memory_gap, terms_gap) if gap]
        if file_gaps:
            return {
                "turn_id": turn_id,
                "status": "blocked",
                "coverage_check": coverage,
                "blockers": {"required_context": file_gaps},
                "resolution_record": None,
            }

        result = self._call_model(
            payload,
            coverage,
            chat_context,
            event_log,
            temporary_memory,
            terms_nomenclature,
            campaign_context,
            dice_result,
        )
        # Cache is a bounded preprocessor result, not a Lead inference. Carry
        # the validated cache lane forward deterministically.
        cache_result = next(
            (item for item in payload.get("specialist_results", []) if isinstance(item, dict) and item.get("specialist") == "cache"),
            {},
        )
        if isinstance(cache_result.get("cache_delta"), dict):
            result["cache_delta"] = cache_result["cache_delta"]
        result["turn_id"] = turn_id
        output = {
            "turn_id": turn_id,
            "mode": payload.get("mode"),
            "request_type": payload.get("request_type"),
            "status": result["status"],
            "coverage_check": coverage,
            "input_sources": {
                "chat_context": "provided",
                "event_log": "markdown_files/🌍 CORE WORLD FRAME (REFINED).md::Event log",
                "temporary_memory": "markdown_files/TEMP_MEMORY.md",
                "terms_nomenclature": "markdown_files/TERMS_AND_NOMENCLATURE.md",
                "campaign_context": "provided" if campaign_context is not None else "not_available",
                "specialists": "provided",
            },
            "resolution_record": result,
        }
        if result["status"] == "needs_clarification":
            request = result.get("clarification_request")
            if not isinstance(request, dict):
                request = {
                    "question": (result.get("notes") or ["Please clarify the intended action."])[0],
                    "why": "The Lead Resolver cannot safely determine the intended resolution.",
                    "options": [],
                }
            output["player_question"] = request
        return output

    @staticmethod
    def _evidence_expansion_request(turn_id: str, coverage: dict[str, Any]) -> dict[str, Any]:
        requests: list[str] = []
        for item in coverage.get("specialist_evidence_requests", []) or []:
            if isinstance(item, dict):
                request = item.get("request") or item.get("description")
            else:
                request = str(item)
            if request and request not in requests:
                requests.append(str(request))
        for item in coverage.get("unresolved_evidence_gaps", []) or []:
            if not isinstance(item, dict):
                continue
            request = item.get("requested_search") or item.get("heading") or item.get("reason")
            if request and request not in requests:
                requests.append(str(request))
        if not requests:
            requests.append("Search the indexed campaign evidence for material facts required by the unresolved specialist gaps.")
        note = (
            f"Lead Resolver cannot resolve {turn_id} yet. Expand indexed evidence for the material gaps below. "
            "Preserve exact entity matching, do not substitute another character or system, and return references only.\n"
            + "\n".join(f"- {request}" for request in requests)
        )
        return {
            "required": True,
            "turn_id": turn_id,
            "evidence_note": note,
            "requests": requests,
            "next_command": "python brain/evidence_bundle.py bundle.json --evidence-note \"<evidence_note>\"",
        }

    @staticmethod
    def _unwrap_specialist_output(data: dict[str, Any]) -> dict[str, Any]:
        if isinstance(data.get("output"), dict) and "specialist_results" in data["output"]:
            payload = dict(data["output"])
            if isinstance(data.get("coverage_check"), dict):
                payload["coverage_check"] = data["coverage_check"]
            return payload
        return data

    def _read_event_log(self) -> tuple[str, dict[str, Any] | None]:
        try:
            content = self.event_log_path.read_text(encoding="utf-8")
        except OSError as exc:
            return "", {"type": "missing_event_log", "source": str(self.event_log_path), "reason": str(exc)}
        lines = content.splitlines()
        start = next(
            (index for index, line in enumerate(lines) if re.match(r"^##\s+Event log\s*$", line, re.I)),
            None,
        )
        if start is None:
            return "", {"type": "missing_event_log_heading", "source": str(self.event_log_path)}
        return "\n".join(lines[start:]).strip(), None

    def _read_temporary_memory(self) -> tuple[str, dict[str, Any] | None]:
        try:
            return self.temporary_memory_path.read_text(encoding="utf-8"), None
        except OSError as exc:
            return "", {"type": "missing_temporary_memory", "source": str(self.temporary_memory_path), "reason": str(exc)}

    def _read_terms_nomenclature(self) -> tuple[str, dict[str, Any] | None]:
        try:
            return self.terms_nomenclature_path.read_text(encoding="utf-8"), None
        except OSError as exc:
            return "", {"type": "missing_terms_nomenclature", "source": str(self.terms_nomenclature_path), "reason": str(exc)}

    def _call_model(
        self,
        payload: dict[str, Any],
        coverage: dict[str, Any],
        chat_context: Any,
        event_log: str,
        temporary_memory: str,
        terms_nomenclature: str,
        campaign_context: Any,
        dice_result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        api_key = self._api_key()
        if not api_key:
            raise RuntimeError("Lead Resolver requires DEEPSEEK_API_KEY or API_KEY")
        request = {
            "chat_context": chat_context,
            "action_frames": payload.get("action_frames", []),
            "selected_sections": payload.get("selected_sections", []),
            "specialist_results": payload.get("specialist_results", []),
            "coverage_check": coverage,
            "event_log": event_log,
            "temporary_memory": temporary_memory,
            "terms_nomenclature": terms_nomenclature,
            "campaign_context": campaign_context if campaign_context is not None else "Not available yet; do not block a valid action solely for this optional source.",
            "dice_result": dice_result if dice_result is not None else "No dice result has been supplied yet.",
        }
        content = ModelGateway(self.repo_root).complete(
            stage="lead_resolver",
            request_id=str(payload.get("turn_id", "")) or None,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            json_mode=True,
            timeout=180,
            messages=[
                {"role": "system", "content": LEAD_PROMPT},
                {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
            ],
        ).content
        if not content:
            raise RuntimeError("Lead Resolver returned an empty response")
        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Lead Resolver returned invalid JSON") from exc
        return self._validate_result(result)

    @staticmethod
    def _validate_result(result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise RuntimeError("Lead Resolver response must be an object")
        required = {
            "status", "clarification_request", "validity", "locked_calculation", "dice_request", "outcome",
            "consequences", "resource_changes", "time_changes", "relationship_changes",
            "xp_changes", "visibility", "mutation_requirements", "conflict_trace", "notes",
        }
        missing = sorted(required - set(result))
        if missing:
            raise RuntimeError(f"Lead Resolver response is missing fields: {', '.join(missing)}")
        if result["status"] not in {"resolved", "awaiting_dice", "blocked", "needs_clarification"}:
            raise RuntimeError("Lead Resolver returned an invalid status")
        result.setdefault("cache_delta", None)
        if result["cache_delta"] is not None and not isinstance(result["cache_delta"], dict):
            raise RuntimeError("Lead Resolver cache_delta must be an object or null")
        if result["validity"] not in {"valid", "invalid", "undetermined"}:
            raise RuntimeError("Lead Resolver returned an invalid validity")
        for field in (
            "consequences", "resource_changes", "time_changes", "relationship_changes",
            "xp_changes", "mutation_requirements", "conflict_trace", "notes",
        ):
            if not isinstance(result[field], list):
                raise RuntimeError(f"Lead Resolver field must be a list: {field}")
        if "modifier_changes" not in result:
            result["modifier_changes"] = []
        elif not isinstance(result["modifier_changes"], list):
            raise RuntimeError("Lead Resolver field must be a list: modifier_changes")
        if "branch_changes" not in result:
            result["branch_changes"] = []
        elif not isinstance(result["branch_changes"], list):
            raise RuntimeError("Lead Resolver field must be a list: branch_changes")
        if result["status"] == "resolved" and result["outcome"] is None:
            raise RuntimeError("Lead Resolver must provide an outcome when status is resolved")
        packet = result.get("narrative_packet")
        if packet is None:
            result["narrative_packet"] = {
                "action_summary": "",
                "scene_context": "",
                "required_beats": [],
                "npc_guidance": [],
                "must_not_add": [],
            }
        elif not isinstance(packet, dict):
            raise RuntimeError("Lead Resolver narrative_packet must be an object")
        if result["status"] == "awaiting_dice" and result["outcome"] is not None:
            raise RuntimeError("Lead Resolver cannot provide an outcome before dice resolution")
        if result["status"] == "awaiting_dice" and not isinstance(result["dice_request"], dict):
            raise RuntimeError("Lead Resolver must provide a dice_request when awaiting dice")
        return result

    @staticmethod
    def _api_key() -> str | None:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        return os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY")


def _load_json(path_or_stdin: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path_or_stdin == "-" else Path(path_or_stdin).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SystemExit("Lead Resolver input must be a JSON object")
    return data


def _load_chat_context(argument: str) -> Any:
    candidate = Path(argument)
    if candidate.is_file():
        text = candidate.read_text(encoding="utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return argument


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Lead Resolver")
    parser.add_argument("specialist_output", help="Specialist result JSON file or '-' for stdin")
    parser.add_argument("--chat-context", required=True, help="Chat context text or JSON file")
    parser.add_argument("--campaign-context", help="Optional campaign context text or JSON file")
    args = parser.parse_args()

    resolver = LeadResolver(Path(__file__).resolve().parent.parent)
    result = resolver.resolve(
        _load_json(args.specialist_output),
        chat_context=_load_chat_context(args.chat_context),
        campaign_context=(
            _load_chat_context(args.campaign_context)
            if args.campaign_context
            else None
        ),
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
