"""Plan off-screen NPC actions from active directives and character state."""

from __future__ import annotations

from typing import Any, Iterable

from .contracts import AutonomyAction, BackgroundDirective, PhasePosition
from .phase_clock import PHASES


class AutonomyResolver:
    """Choose what an NPC attempts; never mark a risky action successful."""

    def plan(
        self,
        directives: Iterable[BackgroundDirective],
        position: PhasePosition,
        *,
        character_state: dict[str, Any] | None = None,
        tick_id: str | None = None,
    ) -> list[AutonomyAction]:
        character_state = character_state or {}
        actions: list[AutonomyAction] = []
        for directive in directives:
            if directive.status != "active":
                continue
            if tick_id and directive.last_processed_tick == tick_id:
                continue
            if directive.started and self._before(position, directive.started):
                continue
            if directive.expires and self._after(position, directive.expires):
                continue

            state = character_state.get(directive.actor, {})
            if not isinstance(state, dict):
                state = {}
            metadata = directive.metadata
            if not isinstance(metadata, dict):
                metadata = {}

            idle_reason = self._idle_reason(directive, state)
            if idle_reason:
                actions.append(AutonomyAction(
                    directive_id=directive.directive_id,
                    actor=directive.actor,
                    assigned_task=directive.task,
                    chosen_action=f"Remain idle: {idle_reason}",
                    location=directive.location,
                    constraints=directive.constraints,
                    requires_resolution=False,
                    visibility=str(metadata.get("visibility", "hidden")),
                    ooc_visibility=str(metadata.get("ooc_visibility", "private")),
                    rationale=idle_reason,
                ))
                continue

            independent_action = state.get("independent_action", metadata.get("independent_action"))
            chosen = str(independent_action).strip() if independent_action else directive.task
            requires_resolution = bool(metadata.get("requires_resolution", True))
            actions.append(AutonomyAction(
                directive_id=directive.directive_id,
                actor=directive.actor,
                assigned_task=directive.task,
                chosen_action=chosen,
                location=directive.location,
                constraints=directive.constraints,
                requires_resolution=requires_resolution,
                visibility=str(metadata.get("visibility", "hidden")),
                ooc_visibility=str(metadata.get("ooc_visibility", "private")),
                rationale=(
                    "Assigned task is compatible with the actor's current state; "
                    "resolve capability, cost, risk, and outcome separately."
                ),
            ))
        return actions

    @staticmethod
    def _idle_reason(directive: BackgroundDirective, state: dict[str, Any]) -> str | None:
        if state.get("unavailable"):
            return str(state.get("unavailable_reason", "actor is unavailable"))
        if state.get("resting"):
            return "actor is resting"
        if state.get("waiting"):
            return "actor is waiting by choice"
        if state.get("hold_position"):
            return "actor was ordered to hold position"
        if state.get("lack_of_tools"):
            return "required tools are unavailable"
        if directive.metadata.get("idle"):
            return str(directive.metadata.get("idle_reason", "no meaningful action is available"))
        return None

    @staticmethod
    def _before(left: PhasePosition, right: PhasePosition) -> bool:
        return AutonomyResolver._ordinal(left) < AutonomyResolver._ordinal(right)

    @staticmethod
    def _after(left: PhasePosition, right: PhasePosition) -> bool:
        return AutonomyResolver._ordinal(left) > AutonomyResolver._ordinal(right)

    @staticmethod
    def _ordinal(position: PhasePosition) -> int:
        try:
            phase_index = PHASES.index(position.phase)
        except ValueError:
            phase_index = 0
        return position.day * len(PHASES) + phase_index
