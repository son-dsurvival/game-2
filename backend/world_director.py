"""Private simulation of world growth, power trajectories, and event seeds.

The World Director owns hidden world state. It never narrates, edits campaign
Markdown, or resolves the player's action. It produces a replayable plan for
the background tick and commits only after that tick resolves successfully.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Callable

from brain.persistence import atomic_json
from .phase_clock import PHASES
from .contracts import PhasePosition


WORLD_STATE_FILE = "brain/state/world_state.json"
PROCESS_STATE_FILE = "brain/state/recurring_processes.json"
FORMULA_STATE_FILE = "brain/state/resource_formulas.json"
DEFAULT_MUTABLE_FIELDS = frozenset({"population", "power", "capacity", "power_cap", "countdown_phases"})


class WorldDirector:
    """Deep module for private world progression and scheduled events."""

    def __init__(
        self,
        repo_root: str | Path = ".",
        *,
        state_path: str | Path | None = None,
        process_state_path: str | Path | None = None,
        formula_path: str | Path | None = None,
    ):
        self.root = Path(repo_root).resolve()
        self.state_path = Path(state_path).resolve() if state_path else self.root / WORLD_STATE_FILE
        self.process_state_path = Path(process_state_path).resolve() if process_state_path else self.root / PROCESS_STATE_FILE
        self.formula_path = Path(formula_path).resolve() if formula_path else self.root / FORMULA_STATE_FILE

    def load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            value = {}
        if not isinstance(value, dict):
            raise RuntimeError("World state is malformed; refusing to reset private world state.")
        return {
            "schema_version": 1,
            "last_position": value.get("last_position"),
            "entities": value.get("entities") if isinstance(value.get("entities"), dict) else {},
            "scheduled_events": value.get("scheduled_events") if isinstance(value.get("scheduled_events"), list) else [],
            "history": value.get("history") if isinstance(value.get("history"), list) else [],
            "committed_ticks": value.get("committed_ticks") if isinstance(value.get("committed_ticks"), list) else [],
            "applied_change_ids": value.get("applied_change_ids") if isinstance(value.get("applied_change_ids"), list) else [],
            "pending_entity_changes": value.get("pending_entity_changes") if isinstance(value.get("pending_entity_changes"), list) else [],
        }

    def upsert_entity(self, entity: dict[str, Any]) -> dict[str, Any]:
        """Register or replace one hidden world entity before simulation begins."""
        if not isinstance(entity, dict) or not str(entity.get("id", "")).strip():
            raise ValueError("A world entity requires an id")
        state = self.load()
        entity_id = str(entity["id"]).strip()
        state["entities"][entity_id] = copy.deepcopy(entity)
        self._write(state)
        return copy.deepcopy(state["entities"][entity_id])

    def apply_entity_changes(self, changes: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        """Apply approved entity deltas atomically and record their audit trail."""
        values = changes if isinstance(changes, list) else [changes]
        state = self.load()
        applied = self._apply_entity_changes_to_state(state, values)
        state["history"] = state["history"][-200:]
        self._write(state)
        return {"status": "applied", "changes": applied}

    def queue_entity_changes(self, changes: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        """Queue Lead-Resolver-approved world changes for the next day batch."""
        values = changes if isinstance(changes, list) else [changes]
        state = self.load()
        applied = {str(item) for item in state.get("applied_change_ids", [])}
        pending = {
            str(item.get("change_id")): item
            for item in state.get("pending_entity_changes", [])
            if isinstance(item, dict) and item.get("change_id")
        }
        for raw in values:
            if not isinstance(raw, dict):
                raise ValueError("Each pending world entity change must be an object")
            change_id = str(raw.get("change_id") or "").strip()
            entity_id = str(raw.get("entity_id") or "").strip()
            field = str(raw.get("field") or "").strip()
            reason = str(raw.get("reason") or "").strip()
            delta = raw.get("delta")
            if not change_id or not entity_id or not field or not reason:
                raise ValueError("Pending world changes require change_id, entity_id, field, and reason")
            if change_id in applied:
                continue
            entity = state["entities"].get(entity_id)
            if not isinstance(entity, dict):
                raise ValueError(f"World entity does not exist: {entity_id}")
            mutable = entity.get("mutable_fields")
            allowed = {str(item) for item in mutable} if isinstance(mutable, list) else set(DEFAULT_MUTABLE_FIELDS)
            if field not in allowed:
                raise ValueError(f"World entity field is not mutable: {entity_id}.{field}")
            if isinstance(delta, bool) or not isinstance(delta, (int, float)) or not math.isfinite(float(delta)):
                raise ValueError(f"World entity delta must be finite numeric: {change_id}")
            pending[change_id] = copy.deepcopy(raw)
        state["pending_entity_changes"] = list(pending.values())
        self._write(state)
        return {"status": "queued", "changes": copy.deepcopy(state["pending_entity_changes"])}

    def advance(
        self,
        previous: PhasePosition | dict[str, Any],
        current: PhasePosition | dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a deterministic hidden-world plan without committing it."""
        previous = self._position(previous)
        current = self._position(current)
        context = context or {}
        state = self.load()
        entities = copy.deepcopy(state["entities"])
        self._merge_context_entities(entities, context.get("world_entities"))
        elapsed_phases = max(0.0, self._phase_index(current) - self._phase_index(previous))
        elapsed_days = max(0, current.day - previous.day)
        updates: list[dict[str, Any]] = []
        scheduled: list[dict[str, Any]] = []

        for entity_id, raw in entities.items():
            if not isinstance(raw, dict) or str(raw.get("status", "active")) not in {"active", "growing"}:
                continue
            before = copy.deepcopy(raw)
            changed = False
            if elapsed_days:
                changed |= self._apply_rate(raw, "population", "growth_per_day", "capacity", elapsed_days)
                changed |= self._apply_rate(raw, "power", "power_per_day", "power_cap", elapsed_days)
            if "countdown_phases" in raw and isinstance(raw.get("countdown_phases"), (int, float)):
                raw["countdown_phases"] = max(0, float(raw["countdown_phases"]) - elapsed_phases)
                if float(raw["countdown_phases"]) <= 0:
                    raw["status"] = "due"
                changed = True
            if changed:
                raw["last_updated"] = current.to_dict()
                updates.append({
                    "entity_id": str(entity_id),
                    "before": before,
                    "after": copy.deepcopy(raw),
                    "visibility": "hidden",
                })
            event = self._event_for_entity(entity_id, raw, current, state["scheduled_events"], scheduled)
            if event is not None:
                scheduled.append(event)

        return {
            "tick_id": self.tick_id(current),
            "previous": previous.to_dict(),
            "current": current.to_dict(),
            "elapsed_phases": elapsed_phases,
            "elapsed_days": elapsed_days,
            "entity_updates": updates,
            "scheduled_events": scheduled,
            "world_state": {"entities": entities, "scheduled_events": state["scheduled_events"]},
            "event_design_requested": bool(scheduled),
        }

    def plan_day(
        self,
        previous: PhasePosition | dict[str, Any],
        current: PhasePosition | dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build one end-of-day world plan without mutating world entities."""
        plan = self.advance(previous, current, context=context)
        state = self.load()
        plan["day_batch"] = True
        plan["pending_entity_changes"] = copy.deepcopy(state.get("pending_entity_changes", []))
        plan["recurring_processes"] = self.plan_processes(previous, current, context=context)
        plan["tick_id"] = f"world-day-{self._position(current).day}"
        return plan

    def commit_day(
        self,
        plan: dict[str, Any],
        *,
        resolution: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Commit automatic growth and all queued day changes exactly once."""
        resolution = dict(resolution or {})
        state = self.load()
        queued = plan.get("pending_entity_changes", []) if isinstance(plan, dict) else []
        explicit = resolution.get("world_entity_changes", [])
        merged: dict[str, dict[str, Any]] = {}
        for item in [*(queued if isinstance(queued, list) else []), *(explicit if isinstance(explicit, list) else [])]:
            if isinstance(item, dict) and item.get("change_id"):
                merged[str(item["change_id"])] = item
        resolution["world_entity_changes"] = list(merged.values())
        result = self.commit(plan, resolution=resolution)
        process_plan = plan.get("recurring_processes") if isinstance(plan, dict) else None
        if result.get("status") in {"committed", "already_committed"} and isinstance(process_plan, dict):
            process_resolution = plan.get("process_resolution")
            if not isinstance(process_resolution, dict):
                process_resolution = resolution.get("process_resolution") if isinstance(resolution.get("process_resolution"), dict) else resolution
            if process_plan.get("processes"):
                self.commit_processes(process_plan, process_resolution)
        if result.get("status") in {"committed", "already_committed"}:
            state = self.load()
            applied = {str(item) for item in state.get("applied_change_ids", [])}
            state["pending_entity_changes"] = [
                item for item in state.get("pending_entity_changes", [])
                if not isinstance(item, dict) or str(item.get("change_id")) not in applied
            ]
            self._write(state)
        return result

    def commit(self, plan: dict[str, Any], *, resolution: dict[str, Any] | None = None) -> dict[str, Any]:
        """Commit a previously planned tick after successful resolution."""
        state = self.load()
        tick_id = str(plan.get("tick_id") or "") if isinstance(plan, dict) else ""
        if tick_id and tick_id in {str(item) for item in state["committed_ticks"]}:
            return {"status": "already_committed", "pending_world_event": self.due_event(plan.get("current", {})), "updates": []}
        world_state = plan.get("world_state") if isinstance(plan, dict) else None
        if isinstance(world_state, dict):
            state["entities"] = world_state.get("entities", state["entities"])
        existing_ids = {str(item.get("id")) for item in state["scheduled_events"] if isinstance(item, dict)}
        for event in plan.get("scheduled_events", []) if isinstance(plan, dict) else []:
            if isinstance(event, dict) and str(event.get("id")) not in existing_ids:
                state["scheduled_events"].append(event)
        entity_changes: list[dict[str, Any]] = []
        if isinstance(resolution, dict):
            raw_entity_changes = resolution.get("world_entity_changes", [])
            if raw_entity_changes:
                if not isinstance(raw_entity_changes, list):
                    raise ValueError("world_entity_changes must be a list")
                entity_changes = self._apply_entity_changes_to_state(state, raw_entity_changes)
            designed = resolution.get("world_event")
            if isinstance(designed, dict):
                event_key = str(designed.get("event_key") or "")
                for event in state["scheduled_events"]:
                    if not isinstance(event, dict):
                        continue
                    if event_key and str(event.get("event_key")) != event_key:
                        continue
                    for key in ("generated_event", "encounter_condition", "latest_phase", "observable_signs"):
                        if key in designed:
                            event[key] = designed[key]
                    break
            for update in resolution.get("world_updates", []):
                if isinstance(update, dict):
                    state["history"].append({**update, "position": plan.get("current")})
        state["last_position"] = plan.get("current")
        if tick_id:
            state["committed_ticks"].append(tick_id)
            state["committed_ticks"] = state["committed_ticks"][-500:]
        state["history"] = state["history"][-200:]
        self._write(state)
        pending = self.due_event(plan.get("current", {}))
        return {
            "status": "committed",
            "pending_world_event": pending,
            "updates": plan.get("entity_updates", []),
            "entity_changes": entity_changes,
        }

    def due_event(self, position: PhasePosition | dict[str, Any]) -> dict[str, Any] | None:
        position = self._position(position)
        state = self.load()
        candidates = []
        for event in state["scheduled_events"]:
            if not isinstance(event, dict) or event.get("status") != "scheduled":
                continue
            earliest = int(event.get("earliest_day", position.day))
            latest = int(event.get("latest_day", earliest))
            if earliest <= position.day <= latest:
                candidates.append(event)
        candidates.sort(key=lambda item: (int(item.get("earliest_day", 0)), str(item.get("id", ""))))
        return copy.deepcopy(candidates[0]) if candidates else None

    def mark_event_encountered(self, event_id: str) -> None:
        state = self.load()
        for event in state["scheduled_events"]:
            if isinstance(event, dict) and str(event.get("id")) == str(event_id):
                event["status"] = "encountered"
        self._write(state)

    def _apply_entity_changes_to_state(self, state: dict[str, Any], changes: list[Any]) -> list[dict[str, Any]]:
        if not isinstance(changes, list):
            raise ValueError("Entity changes must be a list")
        known_ids = {str(item) for item in state.get("applied_change_ids", [])}
        known_ids.update(
            str(item.get("change_id")) for item in state.get("history", [])
            if isinstance(item, dict) and item.get("type") == "world_entity_change" and item.get("change_id")
        )
        batch_ids: set[str] = set()
        prepared: list[tuple[dict[str, Any], dict[str, Any], str, float]] = []
        for raw in changes:
            if not isinstance(raw, dict):
                raise ValueError("Each world entity change must be an object")
            change_id = str(raw.get("change_id") or "").strip()
            entity_id = str(raw.get("entity_id") or "").strip()
            field = str(raw.get("field") or "").strip()
            reason = str(raw.get("reason") or "").strip()
            if not change_id or not entity_id or not field or not reason:
                raise ValueError("World entity changes require change_id, entity_id, field, and reason")
            if change_id in known_ids or change_id in batch_ids:
                raise ValueError(f"Duplicate world entity change_id: {change_id}")
            entity = state["entities"].get(entity_id)
            if not isinstance(entity, dict):
                raise ValueError(f"World entity does not exist: {entity_id}")
            mutable = entity.get("mutable_fields")
            allowed = {str(item) for item in mutable} if isinstance(mutable, list) else set(DEFAULT_MUTABLE_FIELDS)
            if field not in allowed:
                raise ValueError(f"World entity field is not mutable: {entity_id}.{field}")
            before = entity.get(field)
            delta = raw.get("delta")
            if isinstance(before, bool) or not isinstance(before, (int, float)):
                raise ValueError(f"World entity field is not numeric: {entity_id}.{field}")
            if isinstance(delta, bool) or not isinstance(delta, (int, float)) or not math.isfinite(float(delta)):
                raise ValueError(f"World entity delta must be finite numeric: {change_id}")
            prepared.append((entity, raw, field, float(delta)))
            batch_ids.add(change_id)

        applied: list[dict[str, Any]] = []
        for entity, raw, field, delta in prepared:
            before = entity.get(field)
            after_value = float(before) + delta
            if field == "population":
                after_value = max(0.0, after_value)
                capacity = entity.get("capacity")
                if isinstance(capacity, (int, float)) and not isinstance(capacity, bool):
                    after_value = min(after_value, float(capacity))
            after: int | float = int(after_value) if after_value.is_integer() else after_value
            entity[field] = after
            change_id = str(raw["change_id"]).strip()
            record = {
                "change_id": change_id,
                "entity_id": str(raw["entity_id"]).strip(),
                "field": field,
                "requested_delta": raw["delta"],
                "delta": after - before,
                "reason": str(raw["reason"]).strip(),
                "visibility": str(raw.get("visibility") or "hidden"),
                "before": before,
                "after": after,
                "type": "world_entity_change",
            }
            state["history"].append(record)
            state["applied_change_ids"].append(change_id)
            known_ids.add(change_id)
            applied.append(record)
        return applied

    # Recurring process ownership -------------------------------------------------
    # WorldDirector is the single coordinator for world entities and all
    # scheduled world/resource progression. These methods keep recurring
    # process state beside world state while preserving deterministic planning
    # and Lead Resolver approval before any process is advanced.

    def load_processes(self) -> list[dict[str, Any]]:
        state = self._load_process_state()
        return [copy.deepcopy(item) for item in state["processes"] if isinstance(item, dict)]

    def load_formulas(self) -> dict[str, dict[str, Any]]:
        return self._load_formula_catalog()

    def save_formulas(self, formulas: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        if not isinstance(formulas, dict):
            raise ValueError("Formula catalog must be an object")
        normalized = {
            str(formula_id).strip(): copy.deepcopy(formula)
            for formula_id, formula in formulas.items()
            if str(formula_id).strip() and isinstance(formula, dict)
        }
        self.formula_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(self.formula_path, {"schema_version": 1, "formulas": normalized})
        return copy.deepcopy(normalized)

    def upsert_formula(self, formula_id: str, formula: dict[str, Any]) -> dict[str, Any]:
        key = str(formula_id or "").strip()
        if not key or not isinstance(formula, dict):
            raise ValueError("A resource formula requires an id and object definition")
        formulas = self.load_formulas()
        formulas[key] = copy.deepcopy(formula)
        self.save_formulas(formulas)
        return copy.deepcopy(formulas[key])

    def upsert_process(self, process: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_process(process)
        state = self._load_process_state()
        processes = {
            str(item.get("id")): item
            for item in state["processes"]
            if isinstance(item, dict) and item.get("id")
        }
        processes[normalized["id"]] = normalized
        state["processes"] = list(processes.values())
        self._write_process_state(state)
        return copy.deepcopy(normalized)

    def plan_processes(
        self,
        previous: PhasePosition | dict[str, Any],
        current: PhasePosition | dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build due formula-backed process candidates without mutating state."""
        previous = self._position(previous)
        current = self._position(current)
        context = context or {}
        formulas = self._load_formula_catalog()
        due: list[dict[str, Any]] = []
        for raw in self.load_processes():
            if str(raw.get("status", "active")).casefold() not in {"active", "running"}:
                continue
            cycles = self._process_cycles_due(raw, previous, current)
            if cycles <= 0:
                continue
            due.append(self._process_candidate(raw, formulas, cycles, current, context))
        return {
            "tick_id": self.process_tick_id(current),
            "previous": previous.to_dict(),
            "current": current.to_dict(),
            "processes": due,
            "due_count": len(due),
            "status": "due" if due else "no_processes_due",
            "visibility": "private",
        }

    def run_processes(
        self,
        previous: PhasePosition | dict[str, Any],
        current: PhasePosition | dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
        resource_specialist: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        backend_lead_resolver: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Run the Resources-specialist to Backend-Resolver process handoff."""
        context = context or {}
        plan = self.plan_processes(previous, current, context=context)
        if not plan["processes"]:
            return {"status": "no_processes_due", "plan": plan}
        specialist = resource_specialist(plan, context)
        if not isinstance(specialist, dict):
            return {"status": "needs_resolution", "plan": plan, "reason": "Resources specialist returned no handoff."}
        handoff = {
            **plan,
            "resource_specialist": specialist,
            "instructions": "Validate requirements and calculated resource changes; do not invent resources or bypass the ledger.",
        }
        resolution = backend_lead_resolver(handoff, context)
        if not isinstance(resolution, dict) or resolution.get("status") not in {"resolved", "complete"}:
            return {"status": "needs_resolution", "plan": handoff, "resolution": resolution}
        if not self._processes_resolved(handoff, resolution):
            return {"status": "needs_resolution", "plan": handoff, "resolution": resolution}
        commit = self.commit_processes(handoff, resolution)
        return {"status": "complete", "plan": handoff, "resolution": resolution, "commit": commit}

    @staticmethod
    def _processes_resolved(plan: dict[str, Any], resolution: dict[str, Any]) -> bool:
        candidates = plan.get("processes", [])
        values = resolution.get("process_results", [])
        if not candidates:
            return True
        if not isinstance(values, list):
            return False
        statuses = {
            str(item.get("process_id")): str(item.get("status", "")).casefold()
            for item in values
            if isinstance(item, dict) and item.get("process_id")
        }
        return all(
            statuses.get(str(item.get("id"))) in {"applied", "complete", "resolved"}
            for item in candidates if isinstance(item, dict)
        )

    def commit_processes(self, plan: dict[str, Any], resolution: dict[str, Any] | None = None) -> dict[str, Any]:
        """Advance only processes included in a successfully resolved plan."""
        resolution = resolution or {}
        if not self._processes_resolved(plan, resolution):
            return {"status": "needs_resolution", "tick_id": plan.get("tick_id", ""), "processes": []}
        state = self._load_process_state()
        tick_id = str(plan.get("tick_id") or "")
        if tick_id and tick_id in {str(item) for item in state["committed_ticks"]}:
            return {"status": "already_committed", "tick_id": tick_id}
        current = plan.get("current", {})
        changed: list[str] = []
        by_id = {
            str(item.get("id")): item
            for item in state["processes"]
            if isinstance(item, dict) and item.get("id")
        }
        raw_results = resolution.get("process_results", [])
        result_by_id = {
            str(item.get("process_id")): str(item.get("status", "")).casefold()
            for item in raw_results if isinstance(item, dict) and item.get("process_id")
        } if isinstance(raw_results, list) else {}
        for candidate in plan.get("processes", []):
            if not isinstance(candidate, dict) or not candidate.get("id"):
                continue
            process = by_id.get(str(candidate["id"]))
            if process is None:
                continue
            process_id = str(candidate["id"])
            explicit_status = result_by_id.get(process_id)
            if explicit_status and explicit_status not in {"applied", "complete", "resolved"}:
                continue
            if not explicit_status and not candidate.get("eligible"):
                continue
            cycles = int(candidate.get("cycles_due", 1) or 1)
            cadence = max(1.0, float(candidate.get("cadence_phases", 1) or 1))
            next_due = self._process_phase_index(self._position(current)) + cadence * cycles
            process["next_due"] = self._process_position_from_index(next_due).to_dict()
            process["last_processed_tick"] = tick_id or self.process_tick_id(self._position(current))
            process["last_result"] = str(resolution.get("status", "resolved"))
            changed.append(process_id)
        if tick_id:
            state["committed_ticks"].append(tick_id)
            state["committed_ticks"] = state["committed_ticks"][-500:]
        state["history"].append({
            "tick_id": tick_id,
            "position": current,
            "processes": changed,
            "resolution_status": resolution.get("status"),
        })
        state["history"] = state["history"][-200:]
        state["processes"] = list(by_id.values())
        self._write_process_state(state)
        return {"status": "committed", "tick_id": tick_id, "processes": changed}

    def _process_candidate(
        self,
        process: dict[str, Any],
        formulas: dict[str, dict[str, Any]],
        cycles: int,
        current: PhasePosition,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        formula_id = str(process.get("formula_id") or "")
        formula = copy.deepcopy(formulas.get(formula_id, {}))
        if isinstance(process.get("formula"), dict):
            formula.update(copy.deepcopy(process["formula"]))
        process_type = str(process.get("process_type") or formula.get("process_type") or formula.get("type") or "production")
        requirements = self._process_requirements(process, formula)
        requirement_check = self._check_process_requirements(requirements, context)
        changes = self._calculate_process_changes(formula, cycles)
        return {
            "id": str(process["id"]),
            "name": str(process.get("name") or process["id"]),
            "process_type": process_type,
            "formula_id": formula_id or None,
            "formula": formula,
            "requirements": requirements,
            "requirement_check": requirement_check,
            "calculated_changes": changes,
            "cycles_due": cycles,
            "cadence_phases": float(process.get("cadence_phases", formula.get("cadence_phases", 1)) or 1),
            "due_at": process.get("next_due") or process.get("due_at"),
            "position": current.to_dict(),
            "eligible": requirement_check["satisfied"],
            "visibility": "private",
        }

    @staticmethod
    def _process_requirements(process: dict[str, Any], formula: dict[str, Any]) -> list[dict[str, Any]]:
        values: list[Any] = []
        for source in (formula.get("requirements", []), process.get("requirements", [])):
            if isinstance(source, list):
                values.extend(source)
            elif isinstance(source, dict):
                values.extend({"kind": "resource", "resource": key, "amount": value} for key, value in source.items())
        return [dict(item) for item in values if isinstance(item, dict)]

    @staticmethod
    def _check_process_requirements(requirements: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        resources = context.get("resources", context.get("resource_balances", {}))
        if not isinstance(resources, dict):
            resources = {}
        facilities = context.get("facilities", [])
        flags = context.get("flags", {})
        missing: list[dict[str, Any]] = []
        for requirement in requirements:
            kind = str(requirement.get("kind", "resource")).casefold()
            if kind == "resource":
                name = str(requirement.get("resource") or requirement.get("name") or "")
                needed = float(requirement.get("amount", requirement.get("quantity", 0)) or 0)
                available = resources.get(name)
                if not isinstance(available, (int, float)) or float(available) < needed:
                    missing.append({"kind": kind, "resource": name, "required": needed, "available": available})
            elif kind == "facility":
                name = str(requirement.get("name") or requirement.get("facility") or "")
                available = facilities.get(name) if isinstance(facilities, dict) else name in facilities
                if not available:
                    missing.append({"kind": kind, "facility": name})
            elif kind == "flag":
                name = str(requirement.get("name") or requirement.get("flag") or "")
                if not (flags.get(name) if isinstance(flags, dict) else False):
                    missing.append({"kind": kind, "flag": name})
            else:
                missing.append({"kind": kind, "reason": "unsupported requirement kind"})
        return {"satisfied": not missing, "missing": missing}

    @staticmethod
    def _calculate_process_changes(formula: dict[str, Any], cycles: int) -> list[dict[str, Any]]:
        raw = formula.get("resource_changes", formula.get("changes"))
        if not isinstance(raw, list):
            raw = []
            for item in formula.get("inputs", []) if isinstance(formula.get("inputs"), list) else []:
                if isinstance(item, dict):
                    raw.append({**item, "delta": -abs(float(item.get("amount", item.get("quantity", 0)) or 0))})
            for item in formula.get("outputs", []) if isinstance(formula.get("outputs"), list) else []:
                if isinstance(item, dict):
                    raw.append({**item, "delta": abs(float(item.get("amount", item.get("quantity", 0)) or 0))})
        result = []
        for item in raw:
            if not isinstance(item, dict) or not item.get("resource"):
                continue
            delta = item.get("delta", item.get("amount", 0))
            if not isinstance(delta, (int, float)) or isinstance(delta, bool):
                continue
            value = float(delta) * cycles
            result.append({"resource": str(item["resource"]), "delta": int(value) if value.is_integer() else value, "per_cycle": delta, "cycles": cycles})
        return result

    def _process_cycles_due(self, process: dict[str, Any], previous: PhasePosition, current: PhasePosition) -> int:
        due = process.get("next_due", process.get("due_at"))
        if not isinstance(due, dict):
            return 0
        due_index = self._process_phase_index(self._position(due))
        now = self._process_phase_index(current)
        if now < due_index:
            return 0
        cadence = max(1.0, float(process.get("cadence_phases", 1) or 1))
        cycles = int((now - due_index) // cadence) + 1
        return min(cycles, max(1, int(process.get("max_catch_up", 12) or 12)))

    def _load_process_state(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.process_state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            raw = {}
        if not isinstance(raw, dict):
            raise RuntimeError("Recurring process state is malformed; refusing to reset it.")
        return {
            "schema_version": 1,
            "processes": raw.get("processes") if isinstance(raw.get("processes"), list) else [],
            "committed_ticks": raw.get("committed_ticks") if isinstance(raw.get("committed_ticks"), list) else [],
            "history": raw.get("history") if isinstance(raw.get("history"), list) else [],
        }

    def _load_formula_catalog(self) -> dict[str, dict[str, Any]]:
        try:
            raw = json.loads(self.formula_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        values = raw.get("formulas", raw) if isinstance(raw, dict) else {}
        return {str(key): copy.deepcopy(value) for key, value in values.items() if isinstance(value, dict)}

    def _write_process_state(self, state: dict[str, Any]) -> None:
        self.process_state_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(self.process_state_path, state)

    @staticmethod
    def _normalize_process(process: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(process, dict) or not str(process.get("id", "")).strip():
            raise ValueError("Recurring process requires an id")
        value = copy.deepcopy(process)
        value["id"] = str(value["id"]).strip()
        value.setdefault("status", "active")
        if not isinstance(value.get("next_due", value.get("due_at")), dict):
            raise ValueError("Recurring process requires next_due or due_at")
        return value

    @staticmethod
    def _process_phase_index(position: PhasePosition) -> float:
        try:
            phase = PHASES.index(position.phase)
        except ValueError:
            phase = 0
        return position.day * len(PHASES) + phase + position.progress

    @classmethod
    def _process_position_from_index(cls, value: float) -> PhasePosition:
        phase_count = len(PHASES)
        day = int(value // phase_count)
        remainder = value - day * phase_count
        phase_index = min(phase_count - 1, int(remainder))
        progress = remainder - phase_index
        return PhasePosition(day, PHASES[phase_index], round(progress, 8))

    @staticmethod
    def process_tick_id(position: PhasePosition) -> str:
        return f"process-{position.day}-{position.phase}-{position.progress:g}"

    def _event_for_entity(self, entity_id: str, entity: dict[str, Any], current: PhasePosition, existing: list[Any], scheduled: list[dict[str, Any]]) -> dict[str, Any] | None:
        threshold = entity.get("event_threshold")
        population = entity.get("population")
        if threshold is None or not isinstance(population, (int, float)) or population < float(threshold):
            return None
        event_key = str(entity.get("event_key") or f"growth:{entity_id}:{threshold}")
        if any(isinstance(item, dict) and str(item.get("event_key")) == event_key for item in [*existing, *scheduled]):
            return None
        latest_day = current.day + int(entity.get("event_window_days", 2) or 2)
        return {
            "id": f"world-event-{entity_id}-{current.day}",
            "event_key": event_key,
            "status": "scheduled",
            "day": current.day,
            "source_entity": entity_id,
            "generated_event": str(entity.get("event_template") or f"The {entity_id} situation has reached a new pressure point."),
            "encounter_condition": str(entity.get("encounter_condition") or f"The player encounters the consequences of {entity_id} reaching its growth threshold."),
            "earliest_day": current.day,
            "latest_day": latest_day,
            "latest_phase": str(entity.get("latest_phase") or PHASES[-1]),
            "visibility": "hidden",
            "observable_signs": list(entity.get("observable_signs", [])) if isinstance(entity.get("observable_signs"), list) else [],
        }

    @staticmethod
    def _apply_rate(entity: dict[str, Any], value_key: str, rate_key: str, cap_key: str, days: int) -> bool:
        value = entity.get(value_key)
        rate = entity.get(rate_key)
        if not isinstance(value, (int, float)) or not isinstance(rate, (int, float)) or not rate:
            return False
        before = value
        value += rate * days
        cap = entity.get(cap_key)
        if isinstance(cap, (int, float)):
            value = min(value, cap)
        entity[value_key] = int(value) if float(value).is_integer() else value
        return entity[value_key] != before

    @staticmethod
    def _merge_context_entities(target: dict[str, Any], values: Any) -> None:
        if not isinstance(values, list):
            return
        for item in values:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            target[str(item["id"])] = copy.deepcopy(item)

    @staticmethod
    def _position(value: PhasePosition | dict[str, Any]) -> PhasePosition:
        if isinstance(value, PhasePosition):
            return value
        if not isinstance(value, dict):
            raise ValueError("World position must be a PhasePosition or object")
        return PhasePosition(int(value.get("day", 1)), str(value.get("phase", PHASES[0])), float(value.get("progress", 0)))

    @staticmethod
    def _phase_index(position: PhasePosition) -> float:
        try:
            phase = PHASES.index(position.phase)
        except ValueError:
            phase = 0
        return position.day * len(PHASES) + phase + position.progress

    @staticmethod
    def tick_id(position: PhasePosition) -> str:
        return f"world-{position.day}-{position.phase}-{position.progress:g}"

    def _write(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(self.state_path, state)
