"""Orchestrate one sequential background tick per elapsed phase."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import Any, Callable, Iterable

from .autonomy_resolver import AutonomyResolver
from .background_state import BackgroundStateStore
from .contracts import BackgroundTickRecord, PhasePosition
from .phase_clock import PhaseAdvance, PhaseClock
try:
    from brain.specialists.registry import CORE_SPECIALISTS
except ModuleNotFoundError:
    CORE_SPECIALISTS = ("cache", "rules", "character", "special", "create")

Resolver = Callable[[dict[str, Any]], dict[str, Any]]
SpecialistAnalyzer = Callable[[str, dict[str, Any], dict[str, Any]], dict[str, Any]]
CORE_LANES = CORE_SPECIALISTS


class PhaseTickEngine:
    """Run background analysis and commit resolved ticks atomically.

    A missing resolver never guesses success: it returns a plan requiring
    resolution and leaves the directive eligible for a later retry.
    """

    def __init__(
        self,
        state_store: BackgroundStateStore,
        *,
        clock: PhaseClock | None = None,
        autonomy: AutonomyResolver | None = None,
    ):
        self.store = state_store
        self.clock = clock or PhaseClock()
        self.autonomy = autonomy or AutonomyResolver()

    def run(
        self,
        start: PhasePosition,
        phases_elapsed: float,
        *,
        context: dict[str, Any] | None = None,
        resolve_tick: Resolver | None = None,
        analyze: SpecialistAnalyzer | None = None,
        specialist_names: Iterable[str] = CORE_LANES,
    ) -> dict[str, Any]:
        context = context or {}
        transitions = self.clock.advance(start, phases_elapsed)
        result: dict[str, Any] = {
            "status": "complete",
            "start": start.to_dict(),
            "phases_requested": phases_elapsed,
            "ticks": [],
            "plans_requiring_resolution": [],
        }
        for transition in transitions:
            if self.store.has_tick(transition.tick_id):
                result["ticks"].append({"tick_id": transition.tick_id, "status": "already_committed"})
                continue
            directives = self.store.load_directives()
            actions = self.autonomy.plan(
                directives,
                transition.current,
                character_state=context.get("character_state"),
                tick_id=transition.tick_id,
            )
            plan = self._build_plan(transition, actions, context, analyze, specialist_names)
            if plan.get("cache_gate") == "blocked":
                result["status"] = "needs_resolution"
                result["plans_requiring_resolution"].append(plan)
                break
            if resolve_tick is None:
                result["status"] = "needs_resolution"
                result["plans_requiring_resolution"].append(plan)
                break
            resolution = resolve_tick(plan)
            if not isinstance(resolution, dict) or resolution.get("status") not in {"resolved", "complete"}:
                result["status"] = "needs_resolution"
                result["plans_requiring_resolution"].append(plan)
                break
            record = self._record(transition, plan, resolution)
            saved = {**record.to_dict(), 'next_context': resolution.get('next_context'), 'interrupt': resolution.get('interrupt')}
            commit = self.store.commit_tick(saved)
            result["ticks"].append({
                "tick_id": transition.tick_id,
                "status": commit["status"],
                "record": saved,
            })
            if resolution.get('interrupt'):
                result['status'] = 'interrupted'
                result['interrupt'] = resolution['interrupt']
                break
            if isinstance(resolution.get("next_context"), dict):
                context = {**context, **resolution["next_context"]}
        if result["status"] == "complete" and not transitions:
            result["status"] = "no_tick_required"
        return result

    def _build_plan(
        self,
        transition: PhaseAdvance,
        actions: list[Any],
        context: dict[str, Any],
        analyze: SpecialistAnalyzer | None,
        specialist_names: Iterable[str],
    ) -> dict[str, Any]:
        action_data = [item.to_dict() for item in actions]
        plan: dict[str, Any] = {
            "tick_id": transition.tick_id,
            "previous": transition.previous.to_dict(),
            "position": transition.current.to_dict(),
            "actions": action_data,
            "automatic_updates": context.get("automatic_updates", []),
            "instructions": "Resolve each action using normal validity, time, cost, risk, and outcome rules.",
        }
        if analyze is None:
            plan["specialist_analysis"] = []
            return plan
        names = list(dict.fromkeys(specialist_names))
        cache_result = None
        if "cache" in names:
            cache_result = analyze("cache", plan, context)
            if not isinstance(cache_result, dict) or cache_result.get("status") != "complete" or not isinstance(cache_result.get("cache_delta"), dict):
                plan["specialist_analysis"] = [cache_result]
                plan["cache_gate"] = "blocked"
                return plan
            context = {**context, "game_cache": cache_result["cache_delta"]}
            names.remove("cache")
        with ThreadPoolExecutor(max_workers=max(1, len(names))) as executor:
            futures = [executor.submit(copy_context().run, analyze, name, plan, context) for name in names]
            analysis = [future.result() for future in futures]
        plan["specialist_analysis"] = ([cache_result] if cache_result else []) + analysis
        return plan

    @staticmethod
    def _record(
        transition: PhaseAdvance,
        plan: dict[str, Any],
        resolution: dict[str, Any],
    ) -> BackgroundTickRecord:
        actions = resolution.get("actions", plan.get("actions", []))
        if not isinstance(actions, list):
            actions = plan.get("actions", [])
        def list_value(key: str) -> tuple[dict[str, Any], ...]:
            value = resolution.get(key, [])
            return tuple(item for item in value if isinstance(item, dict)) if isinstance(value, list) else ()
        completed = resolution.get("completed_directives", [])
        if not isinstance(completed, list):
            completed = []
        notes = resolution.get("notes", [])
        if not isinstance(notes, list):
            notes = []
        return BackgroundTickRecord(
            tick_id=transition.tick_id,
            position=transition.current,
            actions=tuple(item for item in actions if isinstance(item, dict)),
            automatic_updates=list_value("automatic_updates"),
            resource_changes=list_value("resource_changes"),
            world_updates=list_value("world_updates"),
            visibility_events=list_value("visibility_events"),
            completed_directives=tuple(str(item) for item in completed),
            notes=tuple(str(item) for item in notes),
        )
