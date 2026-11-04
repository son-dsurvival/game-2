"""Private resumable campaign runtime state and stage gates."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from brain.persistence import atomic_json


class RuntimeStateStore:
    """Atomic private state for resume, dice, setup, day-end, and world events."""
    def __init__(self, root: str | Path = ".", path: str | Path = "brain/state/session_runtime.json"):
        self.root = Path(root).resolve()
        self.path = (self.root / path).resolve()

    def load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            value = {}
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError('Runtime state is unreadable; refusing to reset campaign progress.') from exc
        if not isinstance(value, dict):
            raise RuntimeError('Runtime state must be an object.')
        return {
            "schema_version": 1,
            "setup_status": value.get("setup_status", "new"),
            "play_gate": value.get("play_gate", "setup_required"),
            "position": value.get("position", {"day": 1, "phase": "Early Morning", "progress": 0.0}),
            "pending_dice": value.get("pending_dice"),
            "pending_clarification": value.get("pending_clarification"),
            "day_end": value.get("day_end"),
            "pending_world_event": value.get("pending_world_event"),
            "last_receipt": value.get("last_receipt"),
            **value,
        }

    def save(self, state: dict[str, Any]) -> dict[str, Any]:
        state = {**self.load(), **state, "schema_version": 1}
        atomic_json(self.path, state)
        return state

    def transition(self, *, play_gate: str, **changes: Any) -> dict[str, Any]:
        return self.save({"play_gate": play_gate, **changes})

    def can_play(self) -> bool:
        return self.load().get("play_gate") == "open"
