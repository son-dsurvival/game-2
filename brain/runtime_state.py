"""Private resumable campaign runtime state and stage gates."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from brain.persistence import atomic_json


class RuntimeStateStore:
    """Atomic current state plus an append-only private execution journal."""

    def __init__(self, root: str | Path = ".", path: str | Path = "brain/state/session_runtime.json"):
        self.root = Path(root).resolve()
        self.path = (self.root / path).resolve()
        self.journal_path = self.path.with_name("session_runtime_events.jsonl")
        self.player_history_path = self.path.with_name("player_prompt_history.txt")

    def load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            value = {}
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Runtime state is unreadable; refusing to reset campaign progress.") from exc
        if not isinstance(value, dict):
            raise RuntimeError("Runtime state must be an object.")
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

    def replace(self, state: dict[str, Any]) -> dict[str, Any]:
        """Replace the snapshot exactly, used when restoring a journal snapshot."""
        state = {"schema_version": 1, **state}
        atomic_json(self.path, state)
        return state

    def transition(self, *, play_gate: str, **changes: Any) -> dict[str, Any]:
        return self.save({"play_gate": play_gate, **changes})

    def can_play(self) -> bool:
        return self.load().get("play_gate") == "open"

    def append_player_exchange(self, position: dict[str, Any] | None, prompt: str, result: str) -> None:
        """Append a plain player/game transcript for Evidence Bundle history."""
        position = position or {}
        day = position.get('day', '?')
        phase = position.get('phase', '?')
        progress = position.get('progress', 0)
        try:
            progress_text = f"{float(progress or 0) * 100:.0f}%"
        except (TypeError, ValueError):
            progress_text = "0%"
        text = (
            f"Day {day} — {phase} ({progress_text} through phase)\n\n"
            f"Player:\n{str(prompt).strip()}\n\n"
            f"Game:\n{str(result).strip()}\n\n"
        )
        self.player_history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.player_history_path.open('a', encoding='utf-8', newline='\n') as handle:
            handle.write(text)
            handle.flush()
            import os
            os.fsync(handle.fileno())

    def append_event(self, event: str, **fields: Any) -> dict[str, Any]:
        """Append one private, durable journal event without changing the snapshot."""
        payload = {
            "event_id": uuid.uuid4().hex,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str, allow_nan=False) + "\n")
            handle.flush()
            import os
            os.fsync(handle.fileno())
        return payload

    def journal_events(self, *, operation_id: str | None = None) -> list[dict[str, Any]]:
        try:
            lines = self.journal_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        except OSError as exc:
            raise RuntimeError("Runtime journal is unreadable; refusing to resume campaign progress.") from exc
        events: list[dict[str, Any]] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                # A torn final append must not hide earlier durable events.
                continue
            if not isinstance(item, dict):
                continue
            if operation_id is None or item.get("operation_id") == operation_id:
                events.append(item)
        return events

    def latest_event(
        self,
        *,
        operation_id: str | None = None,
        events: Iterable[str] | None = None,
    ) -> dict[str, Any] | None:
        allowed = set(events) if events is not None else None
        for item in reversed(self.journal_events(operation_id=operation_id)):
            if allowed is None or item.get("event") in allowed:
                return item
        return None
