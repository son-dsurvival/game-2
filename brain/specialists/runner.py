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
        SPECIALIST_DEFINITIONS,
        SpecialistDefinition,
        get_specialist,
        validate_created_definition,
    )
    from brain.specialists.branch_registry import BranchRegistry
    from brain.specialists.branch_discovery import BranchDiscovery
    from brain.state.model_gateway import ModelGateway
    from .calculation_contract import CalculationContractError, validate_calculation
except ImportError:  # Direct execution: python brain/specialists/runner.py
    from registry import (
        SPECIALIST_DEFINITIONS,
        SpecialistDefinition,
        get_specialist,
        validate_created_definition,
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from brain.specialists.branch_registry import BranchRegistry
    from brain.specialists.branch_discovery import BranchDiscovery
    from brain.state.model_gateway import ModelGateway
    from calculation_contract import CalculationContractError, validate_calculation

from brain.specialists.modifier_contract import validate_magnitude


SPECIALIST_PROMPT = """You are the {specialist_name} Specialist in an evidence-backed game runtime.

## Scope
Your purpose is:
{purpose}

Answer only these questions:
{questions}

Use only the Evidence Bundle, scoped history, scoped state, and player input in
this request. They are read-only. Do not use unstated campaign memory, invent
facts, resolve the final outcome, roll dice, mutate files, change resources, or
create permanent canon. Treat plausible player-provided facts as provisional
for this request, but report contradictions with established evidence.

## Evidence discipline
- Cite only evidence_id or history_id values in citation_allowlist.
- Never reconstruct citations from paths, headings, or line ranges.
- Keep evidence requests specific to the missing fact or rule.
- Do not repeat the transcript or unrelated evidence in findings.
- Return only work owned by this specialist; do not answer another lane's questions.

## Shared output contract
Return JSON only:
{{
  "specialist": "{specialist_name}",
  "status": "complete|blocked|needs_evidence",
  "citations": [{{"evidence_id": "...", "claim": "..."}}],
  "applicable_rules": [],
  "excluded_rules": [],
  "findings": [],
  "assumptions": [],
  "evidence_requests": [],
  "conflicts": [],
  "recommendation": null
}}

Use concise findings. Recommendations are advisory handoffs, never final
outcomes. Add a specialist-specific field only when the task contract below
requires it.
"""

class SpecialistRunner:
    def __init__(self, repo_root: str | Path = "."):
        self.repo_root = Path(repo_root).resolve()

    @staticmethod
    def _specialist_contract(definition: SpecialistDefinition) -> dict[str, Any]:
        """Return the complete registry-owned contract for one specialist."""
        return {
            "name": definition.name,
            "category": definition.category,
            "purpose": definition.purpose,
            "questions": list(definition.questions),
            "task_prompt": definition.task_prompt,
            "activation_tags": list(definition.activation_tags),
            "sections": list(definition.sections),
            "evidence_requirements": list(definition.evidence_requirements),
        }

    @classmethod
    def _system_prompt(cls, definition: SpecialistDefinition) -> str:
        task_prompt = definition.task_prompt or (
            "No additional task contract is defined. Follow the purpose and questions "
            "only; do not perform another specialist's work."
        )
        return SPECIALIST_PROMPT.format(
            specialist_name=definition.name,
            purpose=definition.purpose,
            questions="\n".join(f"- {question}" for question in definition.questions),
        ) + (
            "\n\n## Registry-owned specialist contract\n"
            "This contract is authoritative for this specialist.\\n"
            f"Category: {definition.category}\\n"
            f"Owned sections: {', '.join(definition.sections) or 'none specified'}\\n"
            f"Evidence requirements: {', '.join(definition.evidence_requirements) or 'none specified'}\n"
            "Task rules:\n" + task_prompt + "\n"
            "Do not infer permissions or duties from another specialist's contract."
        )

    def run(
        self,
        bundle_record: dict[str, Any],
        specialist_names: list[str],
    ) -> dict[str, Any]:
        bundle = bundle_record.get("evidence_bundle", bundle_record)
        # Every caller must declare the specialists for its own scoped task.
        # There is no implicit core lane; this prevents unrelated specialists
        # from receiving evidence or running by default.
        names = list(dict.fromkeys(
            name for name in (specialist_names or [])
            if name not in {"cache", "rules", "character"}
        ))
        branch_discovery = BranchDiscovery(self.repo_root).discover(bundle_record)
        current_turn_candidates = [
            item for item in (branch_discovery.get('candidates', []) if isinstance(branch_discovery, dict) else [])
            if isinstance(item, dict) and any(
                isinstance(signal, dict) and signal.get('kind') in {'current_turn', 'resolved_turn'}
                for signal in item.get('signals', [])
            )
        ]
        if (
            current_turn_candidates
            and not bundle_record.get('setup_batch_id')
            and bundle_record.get('process_type') != 'in_world_discussion'
            and 'create' not in names
        ):
            # A current/resolved turn is the trigger for a Create audit. Old
            # persistent candidates must not add Create to every setup batch or
            # every unrelated normal turn. Discovery still does not unlock a
            # branch or write a specialist definition.
            names.append('create')
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
        # Run only the explicitly requested specialists against their scoped
        # bundles, preserving caller order for deterministic replay.
        results_by_name: dict[str, dict[str, Any]] = {}
        cache_prepared = None
        if cache_prepared is not None:
            definition, section_inputs, _section_gaps, local_bundle = cache_prepared
            cache_result = self._run_one(bundle_record, local_bundle, definition, section_inputs)
            results_by_name[definition.name] = cache_result
        else:
            cache_result = None

        remaining = prepared
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
                branch=name,
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
            # Branch discovery and the catalog are only useful to the lanes
            # that can act on branch coverage. Sending them to every specialist
            # needlessly expands prompts and increases distraction.
            "branch_discovery": bundle.get("branch_discovery", {}) if definition.name in {"special", "create"} else {},
            "action_frames": bundle.get("action_frames", []),
            "routing_record": {
                "mode": bundle_record.get("mode"),
                "process_type": bundle_record.get("process_type", "action"),
                "tags": bundle_record.get("tags", []),
                "required_specialists": bundle_record.get("required_specialists", []),
                "setup_batch_id": bundle_record.get("setup_batch_id"),
                "setup_policy": bundle_record.get("setup_policy", {}),
            },
            "specialist": definition.name,
            "specialist_contract": self._specialist_contract(definition),
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
            ] if definition.name == "create" else [],
        }
        gateway = ModelGateway(self.repo_root)
        messages = [
            {
                "role": "system",
                "content": self._system_prompt(definition),
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
            setup_batch_id=bundle_record.get("setup_batch_id"),
            setup_policy=bundle_record.get("setup_policy", {}),
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
        setup_batch_id: str | None = None,
        setup_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise RuntimeError(f"Specialist {definition.name} did not return an object")
        def supplied(value: Any) -> bool:
            return value is not None and value != "" and value != [] and value != {}
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
        if definition.name in {"create_stat_modifier", "create_effect_modifier"} and result.get("status") == "complete":
            field = "stat_modifier_options" if definition.name == "create_stat_modifier" else "effect_modifier_options"
            options = result.get(field)
            if definition.name == "create_stat_modifier":
                # Stat design is three choices per eligible stat slot, not three total
                # choices across the character. This lets a player compare three
                # low/high-basis directions for each justified stat opportunity.
                if not isinstance(options, list) or not options:
                    result["status"] = "needs_evidence"
                    result.setdefault("conflicts", []).append({
                        "type": "invalid_modifier_option_count",
                        "field": field,
                        "expected": "three options for each eligible stat slot",
                        "actual": len(options) if isinstance(options, list) else None,
                        "reason": "Stat modifier design must provide three choices per eligible stat slot.",
                    })
                else:
                    required = ("name", "stat", "tier", "breadth", "basis_level", "major_or_minor", "magnitude", "description", "evidence", "limitations", "growth_or_conversion_rule")
                    invalid = [
                        index for index, option in enumerate(options)
                        if not isinstance(option, dict) or any(not supplied(option.get(key)) for key in required)
                        or (isinstance(option, dict) and option.get("breadth") != "broad_stat_domain")
                        or (isinstance(option, dict) and option.get("basis_level") not in {"high", "low", "assumed_low"})
                    ]
                    magnitude_invalid = [
                        index for index, option in enumerate(options)
                        if isinstance(option, dict)
                        and not any(not supplied(option.get(key)) for key in ("tier", "magnitude"))
                        and validate_magnitude(option.get("magnitude"), option.get("tier"))
                    ]
                    if magnitude_invalid:
                        result.setdefault("conflicts", []).append({
                            "type": "modifier_magnitude_out_of_tier",
                            "field": field,
                            "options": magnitude_invalid,
                            "reason": "Each modifier magnitude must fit the universal tier band.",
                        })
                        invalid.extend(magnitude_invalid)
                    groups: dict[str, int] = {}
                    order: list[str] = []
                    for option in options:
                        if isinstance(option, dict) and option.get("stat"):
                            stat = str(option["stat"]).strip().upper()
                            groups[stat] = groups.get(stat, 0) + 1
                            if not order or order[-1] != stat:
                                order.append(stat)
                    wrong_groups = {stat: count for stat, count in groups.items() if count != 3}
                    if len(order) != len(groups):
                        result.setdefault("conflicts", []).append({
                            "type": "non_contiguous_modifier_option_groups",
                            "field": field,
                            "reason": "Options for each stat must be grouped contiguously.",
                        })
                        invalid.append(-1)
                    if wrong_groups:
                        result.setdefault("conflicts", []).append({
                            "type": "invalid_modifier_option_group_count",
                            "field": field,
                            "groups": wrong_groups,
                            "expected": 3,
                            "reason": "Each eligible stat slot must have exactly three choices.",
                        })
                        invalid.append(-1)
                    if invalid:
                        result["status"] = "needs_evidence"
                        result.setdefault("conflicts", []).append({
                            "type": "incomplete_modifier_options",
                            "field": field,
                            "options": sorted(set(invalid)),
                            "reason": "Every stat choice needs bounded mechanics, basis labeling, and evidence.",
                        })
            elif setup_batch_id == 'status_effect_modifiers' and (not isinstance(options, list) or len(options) != 10):
                result["status"] = "needs_evidence"
                result.setdefault("conflicts", []).append({
                    "type": "invalid_modifier_option_count",
                    "field": field,
                    "expected": 10,
                    "actual": len(options) if isinstance(options, list) else None,
                    "reason": "Starting Effect Modifier design must provide ten choices from which the player selects three.",
                })
            elif setup_batch_id != 'status_effect_modifiers' and (not isinstance(options, list) or len(options) != 5):
                result["status"] = "needs_evidence"
                result.setdefault("conflicts", []).append({
                    "type": "invalid_modifier_option_count",
                    "field": field,
                    "expected": 5,
                    "actual": len(options) if isinstance(options, list) else None,
                    "reason": "Effect modifier design must return exactly five player choices.",
                })
            else:
                setup_effect = setup_batch_id == 'status_effect_modifiers'
                required = (("name", "basis_level", "tier", "magnitude", "description", "boost_domain", "evidence", "activation_conditions", "limitations", "anti_farming_boundary", "stacking", "placements") if setup_effect else ("name", "tier", "magnitude", "description", "boost_domain", "evidence", "activation_conditions", "limitations", "anti_farming_boundary", "stacking", "placements"))
                invalid = [
                    index for index, option in enumerate(options)
                    if not isinstance(option, dict) or any(not supplied(option.get(key)) for key in required)
                ]
                magnitude_invalid = [
                    index for index, option in enumerate(options)
                    if isinstance(option, dict)
                    and not any(not supplied(option.get(key)) for key in ("tier", "magnitude"))
                    and validate_magnitude(option.get("magnitude"), option.get("tier"))
                ]
                if magnitude_invalid:
                    invalid.extend(magnitude_invalid)
                    result.setdefault("conflicts", []).append({
                        "type": "modifier_magnitude_out_of_tier",
                        "field": field,
                        "options": magnitude_invalid,
                        "reason": "Each modifier magnitude must fit the universal tier band.",
                    })
                if invalid:
                    result["status"] = "needs_evidence"
                    result.setdefault("conflicts", []).append({
                        "type": "incomplete_modifier_options",
                        "field": field,
                        "options": invalid,
                        "reason": "Every effect choice needs bounded mechanics and evidence.",
                    })
                else:
                    # Effect Modifiers are self-contained records. Their
                    # activation, scope, limitations, and stacking rules are
                    # validated on the option itself; no second Modifier Group
                    # placement taxonomy is required.
                    pass
        if definition.name == "class" and setup_batch_id == "status_class_modifiers" and result.get("status") == "complete":
            options = result.get("class_modifier_options")
            required = ("slot", "name", "class", "tier", "basis_level", "magnitude", "description", "evidence", "activation_conditions", "limitations")
            invalid = []
            magnitude_invalid = []
            groups: dict[str, int] = {}
            order: list[str] = []
            if not isinstance(options, list) or not options:
                invalid.append(-1)
            else:
                for index, option in enumerate(options):
                    if not isinstance(option, dict) or any(not supplied(option.get(key)) for key in required):
                        invalid.append(index)
                        continue
                    magnitude_error = validate_magnitude(option.get("magnitude"), option.get("tier"))
                    if magnitude_error:
                        magnitude_invalid.append(index)
                        invalid.append(index)
                    slot = str(option.get("slot"))
                    groups[slot] = groups.get(slot, 0) + 1
                    if not order or order[-1] != slot:
                        order.append(slot)
                if any(count != 5 for count in groups.values()) or len(order) != len(groups):
                    invalid.append(-1)
            if magnitude_invalid:
                result.setdefault("conflicts", []).append({
                    "type": "modifier_magnitude_out_of_tier",
                    "field": "class_modifier_options",
                    "options": sorted(set(magnitude_invalid)),
                    "reason": "Each modifier magnitude must fit the universal tier band.",
                })
            if invalid:
                result["status"] = "needs_evidence"
                result.setdefault("conflicts", []).append({
                    "type": "invalid_class_modifier_options",
                    "field": "class_modifier_options",
                    "options": sorted(set(invalid)),
                    "reason": "Every available Class Modifier slot must provide five contiguous choices and valid tier magnitudes.",
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
            raw_calculation = result.get("calculation")
            result["calculation"] = validate_calculation(
                definition.name,
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
