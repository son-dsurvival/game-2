"""Structured contracts for background phase processing.

These contracts are deliberately independent of the LLM layer. Specialists and
resolvers may produce them, while the state store persists them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PhasePosition:
    day: int
    phase: str
    progress: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"day": self.day, "phase": self.phase, "progress": self.progress}


@dataclass(frozen=True)
class BackgroundDirective:
    directive_id: str
    actor: str
    task: str
    location: str | None = None
    constraints: tuple[str, ...] = ()
    started: PhasePosition | None = None
    expires: PhasePosition | None = None
    status: str = "active"
    last_processed_tick: str | None = None
    assigned_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "directive_id": self.directive_id,
            "actor": self.actor,
            "task": self.task,
            "location": self.location,
            "constraints": list(self.constraints),
            "started": self.started.to_dict() if self.started else None,
            "expires": self.expires.to_dict() if self.expires else None,
            "status": self.status,
            "last_processed_tick": self.last_processed_tick,
            "assigned_by": self.assigned_by,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BackgroundDirective":
        def position(raw: Any) -> PhasePosition | None:
            if not isinstance(raw, dict):
                return None
            try:
                progress = float(raw.get("progress", 0))
                if not 0 <= progress < 1:
                    return None
                return PhasePosition(int(raw["day"]), str(raw["phase"]), progress)
            except (KeyError, TypeError, ValueError):
                return None

        constraints = value.get("constraints", [])
        if not isinstance(constraints, list):
            constraints = []
        metadata = value.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        return cls(
            directive_id=str(value.get("directive_id", "")).strip(),
            actor=str(value.get("actor", "")).strip(),
            task=str(value.get("task", "")).strip(),
            location=(str(value["location"]).strip() if value.get("location") is not None else None),
            constraints=tuple(str(item).strip() for item in constraints if str(item).strip()),
            started=position(value.get("started")),
            expires=position(value.get("expires")),
            status=str(value.get("status", "active")),
            last_processed_tick=(str(value["last_processed_tick"]) if value.get("last_processed_tick") else None),
            assigned_by=(str(value["assigned_by"]) if value.get("assigned_by") else None),
            metadata=metadata,
        )


@dataclass(frozen=True)
class AutonomyAction:
    directive_id: str
    actor: str
    assigned_task: str
    chosen_action: str
    location: str | None
    constraints: tuple[str, ...]
    requires_resolution: bool
    # Roleplay visibility controls narration/character knowledge. OOC
    # visibility independently controls whether the action may be mirrored in
    # Experimentation Register.md; unknown entries stay private by default.
    visibility: str = "hidden"
    ooc_visibility: str = "private"
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "directive_id": self.directive_id,
            "actor": self.actor,
            "assigned_task": self.assigned_task,
            "chosen_action": self.chosen_action,
            "location": self.location,
            "constraints": list(self.constraints),
            "requires_resolution": self.requires_resolution,
            "visibility": self.visibility,
            "ooc_visibility": self.ooc_visibility,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class BackgroundTickRecord:
    tick_id: str
    position: PhasePosition
    actions: tuple[dict[str, Any], ...] = ()
    automatic_updates: tuple[dict[str, Any], ...] = ()
    resource_changes: tuple[dict[str, Any], ...] = ()
    world_updates: tuple[dict[str, Any], ...] = ()
    visibility_events: tuple[dict[str, Any], ...] = ()
    completed_directives: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick_id": self.tick_id,
            "position": self.position.to_dict(),
            "actions": list(self.actions),
            "automatic_updates": list(self.automatic_updates),
            "resource_changes": list(self.resource_changes),
            "world_updates": list(self.world_updates),
            "visibility_events": list(self.visibility_events),
            "completed_directives": list(self.completed_directives),
            "notes": list(self.notes),
        }
