"""Run evidence-backed specialist analyses against a frozen bundle."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
from typing import Any

try:
    from .registry import (
        CORE_SPECIALISTS,
        SPECIALIST_DEFINITIONS,
        SpecialistDefinition,
        get_specialist,
        validate_created_definition,
    )
    from brain.branch_registry import BranchRegistry
    from brain.branch_discovery import BranchDiscovery
    from brain.model_gateway import ModelGateway
    from .calculation_contract import CalculationContractError, validate_calculation
except ImportError:  # Direct execution: python brain/specialists/runner.py
    from registry import (
        CORE_SPECIALISTS,
        SPECIALIST_DEFINITIONS,
        SpecialistDefinition,
        get_specialist,
        validate_created_definition,
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from brain.branch_registry import BranchRegistry
    from brain.branch_discovery import BranchDiscovery
    from brain.model_gateway import ModelGateway
    from calculation_contract import CalculationContractError, validate_calculation


SPECIALIST_PROMPT = """You are the {specialist_name} Specialist in an evidence-backed game runtime.

Your bounded purpose:
{purpose}

Answer only these questions:
{questions}

The Evidence Bundle contains references selected for this turn. The excerpts
below are the read-only source sections you are allowed to inspect. Do not use
unstated campaign memory or invent facts. However, treat facts and premises
stated by the player as provisional canon for this turn when they are plausible
and do not contradict established evidence. Do not demand a Markdown citation
merely because the player supplied the fact directly. Report a contradiction
only when established evidence actually conflicts with it.

The user payload includes a `citation_allowlist` containing the exact evidence
and history IDs supplied to this specialist. Cite only IDs in that allowlist.
Never reconstruct IDs from file paths, headings, or line ranges. A history entry
must use its exact `history_id`; a campaign excerpt must use its exact
`evidence_id`.

For the rules specialist (or the legacy difficulty specialist), calculate
any required task-side target: experiment tier, Difficulty, Novelty, Integration,
Independence, Field Risk, Practice Carryover, and Task Value or Reaction Total.
Do not calculate Action Value in that lane. For the character specialist (or the
legacy modifier specialist), calculate any required action-side components:
relevant stats, skills, tools,
preparation, assistance, Realistic Approach, Practice Carryover on Action, and
resource/time/cost modifiers. Select one positive numeric Realistic Approach
value from the applicable tier band; never leave it at zero for a valid action.
For a spell, mana action, magical attack, or
magical shield/block, use the INT/WIS mental-magic stat basis and inspect the
Status Sheet Modifier Index for matching intelligence, Wisdom, mana, spell,
concentration, systems, and flow modifiers. Do not use STR/END merely because
the word 'block' appears; use physical STR/END only for a genuinely physical
block. For cooperative actions, identify the Main (lead character) and each Sub.
Calculate each participant's own Action Value, then apply the Collaborative
Action / Team Action Value rule: Main Action + Σ(relationship boost between Sub
and Main × Sub Action). In noncombat the relationship boost applies once. Read
relationship tiers from the relationship record; do not replace this formula
with a flat teamwork bonus or averaged stats. If Main/Sub roles are unclear,
request clarification. Shared network effects such as Telepathy, Linked
Cognition, Network Awareness, and Cognitive Relay are separate action-side
modifiers when their scopes match. If the player explicitly says linked
characters are working together and the helper has a real role, they do not
require separate activation. Intent Weaving remains separately activated. Do
not average character stats unless a rule requires it. Do not calculate the
final Task Value or Reaction Total. Infer
values from the player's declared action, procedure, setting, participants,
and the rules. Do not mark all components unresolved merely because the player
did not name the numbers. Use +0 when the rules support no factor, such as a
safely reversible attempt or direct mentor correction, but list every excluded
teamwork modifier and explain why it is excluded. Ask for clarification only
when the action is materially contradictory or genuinely lacks the information
needed to choose between materially different resolutions.

Do not resolve the final outcome, roll dice, mutate files, change resources,
create permanent canon, or override another specialist.

Return JSON only in this shape:
{{
  "specialist": "{specialist_name}",
  "status": "complete|blocked|needs_evidence",
  "citations": [
    {{"evidence_id": "...", "claim": "..."}}
  ],
  "applicable_rules": [],
  "excluded_rules": [],
  "findings": [],
  "assumptions": [],
  "evidence_requests": [],
  "conflicts": [],
  "recommendation": null,
  "calculation": null,
  "world_event": null,
  "cache_delta": null,
  "created_specialists": []
}}

For the rules or difficulty specialist when a numeric task target is needed, calculation must be:
{{
  "kind": "difficulty",
  "target_type": "Task Value|Reaction Total",
  "tier": 0,
  "components": {{"difficulty": 0, "novelty": 0, "integration": 0, "independence": 0, "field_risk": 0, "practice_carryover": 0}},
  "reaction_reference": 0,
  "total": 0,
  "formula": "..."
}}

For the character or modifier specialist when a numeric action value is needed, calculation must be:
{{
  "kind": "modifier",
  "action_type": "physical|magical|spell|mana|social|other",
  "stat_formula": "...",
  "components": [{{"name": "...", "value": 0, "included": true, "reason": "..."}}],
  "realistic_approach": 0,
  "action_value_before_d20": 0,
  "participants": [],
  "team_action": null
}}

Recommendations are advisory findings for the Lead Resolver, never final outcomes.
For the cache specialist, include a `cache_delta` object with these lists:
`durable_facts`, `active_threads`, `pending_commitments`, `unresolved_questions`,
and `expiring_facts`. Each entry must include a concise value and its source
turn or evidence reference. Mark facts as new, confirmed, superseded, or
expired when applicable. Do not copy the entire transcript into the cache.

For the world specialist, when a new world event is generated, include a
`world_event` object with `roll`, `selected_trigger`, `pool_adjustments`,
`event_tier`, `generated_event`, `encounter_condition`, and `latest_phase`.
`encounter_condition` must state the condition that makes the encounter occur
or become available. `latest_phase` must state the final phase in which that
encounter can occur. If the roll selects Nothing or no event is being generated,
`world_event` may be null. Do not put an event proposal only in free-form text.
When asked to prepare a world pool (new-game setup or day-end review), also
return `world_pool`: an object mapping trigger names to explicit integer lists
whose union is 1–100 with no duplicates. Use established rules and state, not
the example pool blindly. A supplied frozen pool must not be modified after its
roll is known.

For the `modifier_creation` specialist, review the supplied history, cache,
experimentation records, existing modifier ledger, and setup draft. Return a
recommendation with `status: none|candidate`, and when candidate include only
`modifier`, `tier`, `description`, `boost_domain`, `evidence`,
`anti_farming_boundary`, and `placements`. Each placement must contain
`group`, `use_in_group`, `activation_conditions`, `limitations`, `stacking`,
`evidence`, and `placement_reason`. Do not award the modifier; the Lead Resolver
decides and emits `modifier_changes`. At new-game setup, a missing action
history means no new effect modifier.

For the create specialist, include a `created_specialists` list only for safe,
recurring uncovered branches. Each item must contain `name` (lowercase snake
case), `purpose`, `questions`, and `activation_tags`; it may also contain a safe
Markdown `template`, bounded `sections`, and `evidence_requirements` that define
how the branch is broken into readable records. Proposals are reviewed by
Python and are not automatically written to the backend. Also list any existing
specialist whose scope needs updating in `findings` rather than silently editing
it. Use the supplied `branch_discovery` report: lore-only candidates are not
established branches; recurring active evidence may justify a proposal, but it
still requires Lead Resolver confirmation and approval.
For rules/character numeric analysis (and legacy difficulty/modifier roles),
put the evidence-backed numeric calculation in recommendation, including each
component, formula, units, and whether a value is exact, bounded, zero, or unresolved. Derive numbers from
player-declared facts and the rules. When a rules band applies and the action is
otherwise clear, choose one numeric value and explain the choice; do not defer
that choice to the Lead Resolver. Use a supported zero when appropriate, and
reserve ranges/unresolved values for genuine contradiction or material
ambiguity. Every factual finding must cite one of the supplied evidence sections or
player history entries. Cite only the supplied evidence_id or history_id; do
not cite file paths or line ranges. Keep findings concise and keep the complete
JSON response compact; escape quotation marks inside string values.
"""


class SpecialistRunner:
    def __init__(self, repo_root: str | Path = "."):
        self.repo_root = Path(repo_root).resolve()

    def run(
        self,
        bundle_record: dict[str, Any],
        specialist_names: list[str],
    ) -> dict[str, Any]:
        bundle = bundle_record.get("evidence_bundle", bundle_record)
        # An empty route is still a normal turn: the four core lanes are always
        # required. Explicit names are retained for replay and for unlocked
        # specialists from older routing records.
        names = list(dict.fromkeys([*CORE_SPECIALISTS, *(specialist_names or [])]))
        branch_discovery = BranchDiscovery(self.repo_root).discover(bundle_record)
        definitions = [self._definition_for(name) for name in names]
        sections = bundle.get("selected_sections", [])
        specialist_bundles = bundle.get("specialist_bundles", {})

        def prepare(definition: SpecialistDefinition) -> tuple[SpecialistDefinition, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
            scoped = specialist_bundles.get(definition.name, {}) if isinstance(specialist_bundles, dict) else {}
            specialist_sections = scoped.get("selected_sections", sections)
            section_inputs, section_gaps = self._read_selected_sections(specialist_sections)
            local_bundle = dict(bundle)
            local_bundle["selected_sections"] = specialist_sections
            local_bundle["evidence_gaps"] = scoped.get("evidence_gaps", bundle.get("evidence_gaps", []))
            local_bundle["history"] = scoped.get("history", bundle.get("conversation_history", []))
            local_bundle["history_breakdown"] = scoped.get("history_breakdown", bundle.get("history_breakdown", []))
            local_bundle["state"] = scoped.get("state", bundle.get("current_state", {}))
            local_bundle["branch_discovery"] = branch_discovery
            citation_allowlist = scoped.get("citation_allowlist")
            if not isinstance(citation_allowlist, dict):
                evidence_ids = sorted({
                    str(section.get("evidence_id") or section.get("id"))
                    for section in specialist_sections
                    if isinstance(section, dict) and (section.get("evidence_id") or section.get("id"))
                })
                history_ids = sorted({
                    str(item.get("history_id"))
                    for item in local_bundle["history"]
                    if isinstance(item, dict) and item.get("history_id")
                })
                citation_allowlist = {
                    "evidence_ids": evidence_ids,
                    "history_ids": history_ids,
                    "all_ids": sorted(set(evidence_ids) | set(history_ids)),
                }
            local_bundle["citation_allowlist"] = citation_allowlist
            return definition, section_inputs, section_gaps, local_bundle

        prepared = [prepare(definition) for definition in definitions]
        # The cache lane runs first so every other specialist receives the
        # latest compact context. The remaining lanes stay concurrent and are
        # collected in route order for deterministic replay.
        results_by_name: dict[str, dict[str, Any]] = {}
        cache_prepared = next((item for item in prepared if item[0].name == "cache"), None)
        if cache_prepared is not None:
            definition, section_inputs, _section_gaps, local_bundle = cache_prepared
            cache_result = self._run_one(bundle_record, local_bundle, definition, section_inputs)
            results_by_name[definition.name] = cache_result
        else:
            cache_result = None

        remaining = [item for item in prepared if item[0].name != "cache"]
        if isinstance(cache_result, dict) and cache_result.get("status") == "blocked":
            remaining = []
        cache_delta = cache_result.get("cache_delta") if isinstance(cache_result, dict) else None
        if not isinstance(cache_delta, dict):
            cache_delta = {}
        for _definition, _section_inputs, _section_gaps, local_bundle in remaining:
            local_bundle["game_cache"] = cache_delta
        with ThreadPoolExecutor(max_workers=max(1, len(remaining))) as executor:
            futures = [
                executor.submit(copy_context().run, self._run_one, bundle_record, local_bundle, definition, section_inputs)
                for definition, section_inputs, _section_gaps, local_bundle in remaining
            ]
            for (definition, _section_inputs, _section_gaps, _local_bundle), future in zip(remaining, futures):
                results_by_name[definition.name] = future.result()
        results = [results_by_name[definition.name] for definition in definitions if definition.name in results_by_name]

        all_section_gaps = [
            {**gap, "specialist": definition.name}
            for definition, _inputs, section_gaps, _bundle in prepared
            for gap in section_gaps
        ]
        completed = [item["specialist"] for item in results if item["status"] == "complete"]
        failed = [item["specialist"] for item in results if item["status"] != "complete"]
        created = [
            proposal
            for item in results
            if item.get("specialist") == "create"
            for proposal in item.get("created_specialists", [])
            if isinstance(proposal, dict)
        ]
        return {
            "turn_id": bundle_record.get("turn_id", bundle.get("turn_id")),
            "action_frames": bundle.get("action_frames", []),
            "selected_sections": sections,
            "evidence_gaps": bundle.get("evidence_gaps", []),
            "gap_adjudication": bundle.get("gap_adjudication", bundle_record.get("gap_adjudication")),
            "specialist_results": results,
            "specialist_updates": {
                "created_specialists": created,
                "game_cache": (cache_result or {}).get("cache_delta"),
                "branch_discovery": branch_discovery,
                "note": "Discovery identifies evidence-backed candidates; proposals are bounded and require Lead confirmation and approval before becoming an unlocked route.",
            },
            "coverage": {
                "required": names,
                "completed": completed,
                "failed_or_blocked": failed,
                "section_gaps": all_section_gaps,
            },
        }

    def _definition_for(self, name: str) -> SpecialistDefinition:
        try:
            return get_specialist(name)
        except ValueError:
            entry = BranchRegistry(self.repo_root).entry(name)
            if not entry or str(entry.get("status", "locked")).casefold() != "unlocked":
                raise
            activation = entry.get("activation_tags", [])
            if isinstance(activation, str):
                activation = [activation]
            questions = entry.get("questions", [])
            if isinstance(questions, str):
                questions = [questions]
            if not isinstance(questions, list) or not questions:
                questions = [
                    f"Which {name} branch facts and rules apply?",
                    f"What {name} state, costs, risks, and consequences matter?",
                    f"What {name} evidence is missing or contradictory?",
                ]
            sections = entry.get("sections", [])
            if isinstance(sections, str):
                sections = [sections]
            evidence = entry.get("evidence_requirements", [])
            if isinstance(evidence, str):
                evidence = [evidence]
            return SpecialistDefinition(
                name=name,
                purpose=str(entry.get("purpose") or f"Monitor the unlocked {name} branch and its world-specific state, rules, and consequences."),
                questions=tuple(str(question) for question in questions[:8]),
                activation_tags=tuple(str(tag) for tag in activation),
                category="special",
                unlockable=True,
                description=str(entry.get("reason", "Dynamically unlocked special branch.")),
                template=str(entry.get("template")) if entry.get("template") else None,
                sections=tuple(str(section) for section in sections[:12]),
                evidence_requirements=tuple(str(item) for item in evidence[:12]),
            )

    def _run_one(
        self,
        bundle_record: dict[str, Any],
        bundle: dict[str, Any],
        definition: SpecialistDefinition,
        section_inputs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        api_key = self._api_key()
        if not api_key:
            raise RuntimeError("Specialist analysis requires DEEPSEEK_API_KEY or API_KEY")
        scoped_history = bundle.get("history", bundle.get("conversation_history", []))
        scoped_state = bundle.get("state", bundle.get("current_state", {}))
        model_evidence_sections = [
            {
                "evidence_id": section.get("evidence_id", section.get("id")),
                "section": section.get("name"),
                "source_type": section.get("source_type", "campaign_file"),
                "text": section.get("text", section.get("excerpt", "")),
            }
            for section in section_inputs
        ]
        payload = {
            "player_input": bundle.get("player_input", {}),
            "conversation_history": scoped_history,
            "history_breakdown": bundle.get("history_breakdown", []),
            "current_state": scoped_state,
            "game_cache": scoped_state.get("game_cache") if isinstance(scoped_state, dict) else bundle.get("game_cache"),
            "branch_discovery": bundle.get("branch_discovery", {}),
            "action_frames": bundle.get("action_frames", []),
            "routing_record": {
                "mode": bundle_record.get("mode"),
                "tags": bundle_record.get("tags", []),
                "required_specialists": bundle_record.get("required_specialists", []),
            },
            "specialist": definition.name,
            "evidence_sections": model_evidence_sections,
            "citation_allowlist": bundle.get("citation_allowlist", {}),
            "admin_request": bundle_record.get("admin_request", {}),
            "specialist_catalog": [
                {
                    "name": item.name,
                    "category": item.category,
                    "unlockable": item.unlockable,
                    "purpose": item.purpose,
                    "activation_tags": list(item.activation_tags),
                }
                for item in SPECIALIST_DEFINITIONS.values()
            ],
        }
        gateway = ModelGateway(self.repo_root)
        messages = [
            {
                "role": "system",
                "content": SPECIALIST_PROMPT.format(
                    specialist_name=definition.name,
                    purpose=definition.purpose,
                    questions="\n".join(f"- {question}" for question in definition.questions),
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        content = gateway.complete(
            stage=f"specialist.{definition.name}",
            request_id=str(bundle_record.get("turn_id", "")) or None,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            json_mode=True,
            messages=messages,
        ).content
        if not content:
            raise RuntimeError(f"Specialist {definition.name} returned an empty response")
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Retry once with a compact-output instruction. DeepSeek can emit
            # malformed JSON when a specialist recommendation becomes verbose.
            repaired = gateway.complete(
                stage=f"specialist.{definition.name}.json_repair",
                request_id=str(bundle_record.get("turn_id", "")) or None,
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                json_mode=True,
                messages=[*messages, {"role": "user", "content": "Previous output was invalid JSON. Return a compact valid JSON object only; keep findings and recommendation concise and escape all strings correctly."}],
            ).content
            if not repaired:
                raise RuntimeError(f"Specialist {definition.name} returned an empty repair response")
            try:
                result = json.loads(repaired)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Specialist {definition.name} returned invalid JSON after retry") from exc
        return self._validate_result(
            result,
            definition,
            section_inputs,
            history=scoped_history if isinstance(scoped_history, list) else [],
            citation_allowlist=bundle.get("citation_allowlist"),
        )

    def _read_selected_sections(
        self, sections: Any
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not isinstance(sections, list):
            return [], [{"type": "malformed_sections", "reason": "selected_sections is not a list"}]
        inputs: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []
        for section in sections:
            if not isinstance(section, dict):
                gaps.append({"type": "malformed_section", "reason": "section is not an object"})
                continue
            source = section.get("source")
            location = section.get("location")
            if not isinstance(source, str) or not isinstance(location, str):
                gaps.append({"type": "malformed_section", "section": section.get("id")})
                continue
            path = self._safe_source_path(source)
            line_range = self._line_range(location)
            if path is None or line_range is None:
                gaps.append({"type": "invalid_section_reference", "section": section.get("id")})
                continue
            if not path.is_file():
                gaps.append({"type": "missing_source", "source": source})
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            start, end = line_range
            if start < 1 or end < start or start > len(lines):
                gaps.append({"type": "invalid_line_range", "source": source, "location": location})
                continue
            excerpt = str(section.get("text") or "\n".join(lines[start - 1:min(end, len(lines))]))
            inputs.append({
                "evidence_id": section.get("id"),
                "id": section.get("id"),
                "name": section.get("name"),
                "source": source,
                "source_type": "campaign_file",
                "heading": section.get("name"),
                "location": location,
                "path": section.get("path", []),
                "description": section.get("description", ""),
                "text": excerpt,
                "excerpt": excerpt,
            })
        return inputs, gaps

    def _validate_result(
        self,
        result: Any,
        definition: SpecialistDefinition,
        sections: list[dict[str, Any]],
        *,
        history: list[dict[str, Any]] | None = None,
        citation_allowlist: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise RuntimeError(f"Specialist {definition.name} did not return an object")
        if result.get("specialist") != definition.name:
            raise RuntimeError(f"Specialist identity mismatch for {definition.name}")
        if result.get("status") not in {"complete", "blocked", "needs_evidence"}:
            raise RuntimeError(f"Specialist {definition.name} returned an invalid status")
        for field in (
            "citations", "applicable_rules", "excluded_rules", "findings",
            "assumptions", "evidence_requests", "conflicts",
        ):
            if not isinstance(result.get(field, []), list):
                raise RuntimeError(f"Specialist {definition.name} returned a malformed {field}")

        if definition.name == "cache":
            cache_delta = result.get("cache_delta")
            required_cache_lists = (
                "durable_facts", "active_threads", "pending_commitments",
                "unresolved_questions", "expiring_facts",
            )
            if not isinstance(cache_delta, dict):
                result["status"] = "needs_evidence" if result["status"] == "complete" else result["status"]
                result.setdefault("conflicts", []).append({
                    "type": "malformed_cache_delta",
                    "reason": "cache_delta must be an object with the five cache lists.",
                })
            else:
                missing_or_malformed = [
                    field for field in required_cache_lists
                    if not isinstance(cache_delta.get(field), list)
                ]
                if missing_or_malformed:
                    result["status"] = "needs_evidence" if result["status"] == "complete" else result["status"]
                    result.setdefault("conflicts", []).append({
                        "type": "incomplete_cache_delta",
                        "fields": missing_or_malformed,
                        "reason": "Cache output must use bounded lists rather than transcript text.",
                    })
        if definition.name == "world":
            world_event = result.get("world_event")
            if world_event is not None:
                required_event_fields = (
                    "roll", "selected_trigger", "pool_adjustments", "event_tier",
                    "generated_event", "encounter_condition", "latest_phase",
                )
                if not isinstance(world_event, dict):
                    result["status"] = "needs_evidence" if result["status"] == "complete" else result["status"]
                    result.setdefault("conflicts", []).append({
                        "type": "malformed_world_event",
                        "reason": "world_event must be an object or null.",
                    })
                else:
                    missing = [field for field in required_event_fields if field not in world_event or world_event[field] is None]
                    if missing:
                        result["status"] = "needs_evidence" if result["status"] == "complete" else result["status"]
                        result.setdefault("conflicts", []).append({
                            "type": "incomplete_world_event",
                            "missing": missing,
                            "reason": "Generated world events require encounter_condition and latest_phase.",
                        })
                    if not isinstance(world_event.get("pool_adjustments", []), list):
                        result["status"] = "needs_evidence" if result["status"] == "complete" else result["status"]
                        result.setdefault("conflicts", []).append({
                            "type": "malformed_world_event_pool_adjustments",
                            "reason": "pool_adjustments must be a list.",
                        })
        if definition.name == "modifier_creation":
            recommendation = result.get("recommendation")
            if recommendation is not None:
                if not isinstance(recommendation, dict) or recommendation.get("status") not in {"none", "candidate"}:
                    result["status"] = "needs_evidence" if result["status"] == "complete" else result["status"]
                    result.setdefault("conflicts", []).append({
                        "type": "malformed_modifier_creation_recommendation",
                        "reason": "modifier_creation recommendation must be an object with status none or candidate.",
                    })
                elif recommendation.get("status") == "candidate":
                    required = ("modifier", "tier", "description", "boost_domain", "evidence", "anti_farming_boundary", "placements")
                    missing = [field for field in required if not recommendation.get(field)]
                    placements = recommendation.get("placements")
                    if missing or not isinstance(placements, list) or not placements:
                        result["status"] = "needs_evidence" if result["status"] == "complete" else result["status"]
                        result.setdefault("conflicts", []).append({
                            "type": "incomplete_modifier_creation_recommendation",
                            "missing": missing or ["placements"],
                            "reason": "A modifier candidate needs evidence and at least one practical group placement.",
                        })
                    else:
                        placement_fields = ("group", "use_in_group", "activation_conditions", "limitations", "stacking", "evidence", "placement_reason")
                        invalid = [
                            index for index, placement in enumerate(placements)
                            if not isinstance(placement, dict) or any(not placement.get(field) for field in placement_fields)
                        ]
                        if invalid:
                            result["status"] = "needs_evidence" if result["status"] == "complete" else result["status"]
                            result.setdefault("conflicts", []).append({
                                "type": "incomplete_modifier_group_placements",
                                "placements": invalid,
                                "reason": "Every proposed group placement needs scenario use, limits, stacking, evidence, and rationale.",
                            })
        if definition.name == "create":
            proposals = result.get("created_specialists", result.get("specialist_proposals", []))
            if not isinstance(proposals, list):
                raise RuntimeError("Create Specialist returned a malformed created_specialists list")
            accepted = []
            rejected = []
            for proposal in proposals:
                created = validate_created_definition(proposal)
                if created is None:
                    rejected.append({"proposal": proposal, "reason": "invalid, duplicate, or unsafe specialist definition"})
                    continue
                accepted.append({
                    "name": created.name,
                    "purpose": created.purpose,
                    "questions": list(created.questions),
                    "activation_tags": list(created.activation_tags),
                    "category": created.category,
                    "unlockable": created.unlockable,
                    "template": created.template,
                    "sections": list(created.sections),
                    "evidence_requirements": list(created.evidence_requirements),
                    "status": "proposed",
                })
            result["created_specialists"] = accepted
            if rejected:
                result.setdefault("conflicts", []).extend(rejected)
                result.setdefault("evidence_requests", []).append({
                    "type": "specialist_creation_review",
                    "request": "review rejected specialist proposals",
                    "reason": "Create Specialist proposals must be bounded and unique.",
                })

        valid_citations, invalid_citations = self._validate_citations(
            result['citations'], sections, definition.name, history, citation_allowlist
        )
        result["citations"] = valid_citations
        if invalid_citations:
            # A model citation outside the frozen bundle is an evidence gap,
            # not a pipeline-fatal error. Lead Resolver may review the handoff
            # while keeping the unsupported citation out of the record.
            result["status"] = "needs_evidence" if result["status"] == "complete" else result["status"]
            result.setdefault("evidence_requests", []).extend(invalid_citations)
            result.setdefault("conflicts", []).extend(invalid_citations)
        if "recommendation" not in result:
            result["recommendation"] = None
        if definition.name == "world":
            result.setdefault("world_event", None)
        if definition.name == "cache":
            result.setdefault("cache_delta", {
                "durable_facts": [],
                "active_threads": [],
                "pending_commitments": [],
                "unresolved_questions": [],
                "expiring_facts": [],
            })
        try:
            calculation_owner = {
                "rules": "difficulty",
                "character": "modifier",
            }.get(definition.name, definition.name)
            raw_calculation = result.get("calculation")
            # Core lanes cover many non-roll turns. A null calculation is valid
            # there; when a numeric contract is needed, the model must still
            # provide the structured contract and it is validated below.
            if definition.name in {"rules", "character"} and raw_calculation is None:
                result["calculation"] = None
            else:
                result["calculation"] = validate_calculation(
                    calculation_owner,
                    raw_calculation,
                    status=result["status"],
                )
        except CalculationContractError as exc:
            result["status"] = "needs_evidence" if result["status"] == "complete" else result["status"]
            result.setdefault("conflicts", []).append({
                "type": "invalid_calculation_contract",
                "reason": str(exc),
            })
            result.setdefault("evidence_requests", []).append({
                "type": "calculation_contract",
                "request": "repair the specialist numeric calculation",
                "reason": str(exc),
            })
        return result

    def _validate_citations(
        self,
        citations: list[Any],
        sections: list[dict[str, Any]],
        specialist_name: str,
        history: list[dict[str, Any]] | None = None,
        citation_allowlist: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        valid: list[dict[str, Any]] = []
        invalid: list[dict[str, Any]] = []
        if isinstance(citation_allowlist, dict):
            evidence_ids = {
                str(value) for value in citation_allowlist.get('evidence_ids', [])
                if isinstance(value, str) and value
            }
            history_ids = {
                str(value) for value in citation_allowlist.get('history_ids', [])
                if isinstance(value, str) and value
            }
        else:
            evidence_ids = {
                str(section.get('evidence_id') or section.get('id'))
                for section in sections
                if isinstance(section, dict) and (section.get('evidence_id') or section.get('id'))
            }
            history_ids = {
                str(item.get('history_id'))
                for item in (history or [])
                if isinstance(item, dict) and item.get('history_id')
            }
        for citation in citations:
            if not isinstance(citation, dict):
                invalid.append({'type': 'invalid_citation', 'reason': 'Citation was not an object.'})
                continue
            citation_id = citation.get('evidence_id') or citation.get('history_id')
            if not isinstance(citation_id, str) or not citation_id:
                invalid.append({
                    'type': 'invalid_citation',
                    'reason': f'{specialist_name} must cite an evidence_id or history_id.',
                    'citation': citation,
                })
                continue
            if citation_id not in evidence_ids and citation_id not in history_ids:
                invalid.append({
                    'type': 'citation_outside_frozen_bundle',
                    'reason': f'{specialist_name} cited an ID outside its supplied citation allowlist.',
                    'citation': citation,
                })
                continue
            valid.append(citation)
        return valid, invalid

    @staticmethod
    def _contained(inner: tuple[int, int] | None, outer: tuple[int, int] | None) -> bool:
        return bool(inner and outer and outer[0] <= inner[0] <= inner[1] <= outer[1])

    def _safe_source_path(self, source: str) -> Path | None:
        if not source.startswith("markdown_files/"):
            return None
        root = (self.repo_root / "markdown_files").resolve()
        candidate = (self.repo_root / source).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
        return candidate

    @staticmethod
    def _line_range(location: str) -> tuple[int, int] | None:
        match = re.fullmatch(r"lines?\s+(\d+)-(\d+)", location.strip())
        return (int(match.group(1)), int(match.group(2))) if match else None

    @staticmethod
    def _api_key() -> str | None:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        return os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY")


def _load_bundle(path_or_stdin: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path_or_stdin == "-" else Path(path_or_stdin).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("evidence_bundle", data), dict):
        raise SystemExit("Input must be an Evidence Bundle JSON object")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Run specialists against a frozen Evidence Bundle")
    parser.add_argument("bundle", help="Evidence Bundle JSON file or '-' for stdin")
    parser.add_argument("--specialist", action="append", dest="specialists")
    parser.add_argument("--all", action="store_true", help="Run all registered specialists")
    args = parser.parse_args()

    bundle = _load_bundle(args.bundle)
    required = bundle.get("required_specialists", [])
    names = list(SPECIALIST_DEFINITIONS) if args.all else (args.specialists or required)
    unknown = [name for name in names if name not in SPECIALIST_DEFINITIONS]
    if unknown:
        raise SystemExit(f"Unknown specialists: {', '.join(unknown)}")
    result = SpecialistRunner(Path(__file__).resolve().parent.parent.parent).run(bundle, names)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
