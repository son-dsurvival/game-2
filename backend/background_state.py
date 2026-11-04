"""Split private background state from the player-readable experiment register.

``brain/state/background_state.json`` is the complete runtime record. The
Experimentation Register is only an out-of-character mirror of entries that are
explicitly safe teammate/background status; true surprises never reach it until
revealed through normal play.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Iterable

from .contracts import BackgroundDirective, BackgroundTickRecord

EXPERIMENTATION_REGISTER = "markdown_files/Experimentation Register.md"
PRIVATE_BACKGROUND_STATE = "brain/state/background_state.json"
DIRECTIVES_HEADING = "## Active Background Directives"
TICKS_HEADING = "## Outside Player Perspective Turns"
OOC_VISIBLE = {"teammate_status", "background_status", "ooc_visible", "public"}


class BackgroundStateStore:
    """Persist complete background state privately and mirror safe status only."""

    def __init__(
        self,
        register_path: str | Path = EXPERIMENTATION_REGISTER,
        *,
        private_state_path: str | Path | None = None,
        temp_memory_path: str | Path | None = None,
        mirror: bool = False,
    ):
        # temp_memory_path remains a compatibility alias for a caller-provided
        # public mirror path. It is no longer the authoritative backend store.
        self.register_path = Path(temp_memory_path or register_path).resolve()
        self.mirror = mirror
        if mirror and 'markdown_files' in self.register_path.parts:
            raise ValueError('Automatic mirrors cannot target permanent campaign documents.')
        if private_state_path is not None:
            self.private_state_path = Path(private_state_path).resolve()
        else:
            repo_root = self._repo_root_for(self.register_path)
            self.private_state_path = repo_root / PRIVATE_BACKGROUND_STATE

    def load_directives(self) -> list[BackgroundDirective]:
        return [
            BackgroundDirective.from_dict(item)
            for item in self._private().get("directives", [])
            if isinstance(item, dict)
        ]

    def save_directives(self, directives: Iterable[BackgroundDirective | dict[str, Any]]) -> None:
        values = []
        for item in directives:
            directive = item if isinstance(item, BackgroundDirective) else BackgroundDirective.from_dict(item)
            if directive.directive_id and directive.actor and directive.task:
                values.append(directive)
        state = self._private()
        state["directives"] = [item.to_dict() for item in values]
        self._write_private(state)
        self._write_public_register(values, self.load_ticks())

    def upsert_directive(self, directive: BackgroundDirective | dict[str, Any]) -> None:
        value = directive if isinstance(directive, BackgroundDirective) else BackgroundDirective.from_dict(directive)
        current = {item.directive_id: item for item in self.load_directives()}
        current[value.directive_id] = value
        self.save_directives(current.values())

    def load_ticks(self) -> list[dict[str, Any]]:
        """Return complete records for runtime use; never use this for narration."""
        return [item for item in self._private().get("ticks", []) if isinstance(item, dict)]

    def has_tick(self, tick_id: str) -> bool:
        return any(item.get("tick_id") == tick_id for item in self.load_ticks())

    def load_pending_world_events(self) -> list[dict[str, Any]]:
        """Return private unrevealed world events to the scheduler/resolver only."""
        return [item for item in self._private().get("pending_world_events", []) if isinstance(item, dict)]

    def save_pending_world_events(self, events: Iterable[dict[str, Any]]) -> None:
        state = self._private()
        state["pending_world_events"] = [dict(item) for item in events if isinstance(item, dict)]
        self._write_private(state)

    def commit_tick(self, tick: BackgroundTickRecord | dict[str, Any]) -> dict[str, Any]:
        """Commit the full tick privately, then update the safe OOC mirror."""
        record = tick.to_dict() if isinstance(tick, BackgroundTickRecord) else dict(tick)
        tick_id = str(record.get("tick_id", "")).strip()
        if not tick_id:
            raise ValueError("A background tick requires tick_id")
        state = self._private()
        if any(item.get("tick_id") == tick_id for item in state["ticks"] if isinstance(item, dict)):
            return {"status": "already_committed", "tick_id": tick_id}

        directives = {
            item.directive_id: item
            for item in (BackgroundDirective.from_dict(raw) for raw in state["directives"] if isinstance(raw, dict))
            if item.directive_id
        }
        completed = {str(item) for item in record.get("completed_directives", [])}
        for action in record.get("actions", []):
            if not isinstance(action, dict) or action.get("directive_id") not in directives:
                continue
            directive_id = str(action["directive_id"])
            current = directives[directive_id]
            directives[directive_id] = BackgroundDirective(
                **{
                    **current.__dict__,
                    "status": "completed" if directive_id in completed else current.status,
                    "last_processed_tick": tick_id,
                }
            )
        for directive_id in completed:
            if directive_id in directives:
                current = directives[directive_id]
                directives[directive_id] = BackgroundDirective(
                    **{**current.__dict__, "status": "completed", "last_processed_tick": tick_id}
                )

        state["directives"] = [item.to_dict() for item in directives.values()]
        state["ticks"].append(record)
        self._write_private(state)
        self._write_public_register(directives.values(), state["ticks"])
        public_record = self._public_tick(record)
        return {
            "status": "committed",
            "tick_id": tick_id,
            "directives": len(directives),
            "publicly_mirrored": self.mirror and public_record is not None,
        }

    def _private(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.private_state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raw = {}
        if not isinstance(raw, dict):
            raise RuntimeError('Private background state is malformed; refusing to reset it.')
        return {
            "schema_version": 1,
            "directives": raw.get("directives") if isinstance(raw.get("directives"), list) else [],
            "ticks": raw.get("ticks") if isinstance(raw.get("ticks"), list) else [],
            "pending_world_events": raw.get("pending_world_events") if isinstance(raw.get("pending_world_events"), list) else [],
        }

    def _write_private(self, state: dict[str, Any]) -> None:
        self.private_state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.private_state_path.with_suffix(self.private_state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._replace_with_retry(temporary, self.private_state_path)

    def _write_public_register(
        self,
        directives: Iterable[BackgroundDirective],
        ticks: Iterable[dict[str, Any]],
    ) -> None:
        if not self.mirror:
            return
        content = self._read_public()
        content = self._replace_section_content(content, DIRECTIVES_HEADING, self._render_directives(directives))
        content = self._replace_section_content(content, TICKS_HEADING, self._render_ticks(ticks))
        self._write_public(content)

    def _render_directives(self, directives: Iterable[BackgroundDirective]) -> str:
        visible = [item for item in directives if self._directive_is_public(item)]
        lines = [DIRECTIVES_HEADING, "", "Only explicitly safe teammate/background status is mirrored here. Complete directive metadata remains private runtime state.", ""]
        if not visible:
            lines.append("No player-readable background directives.")
            return "\n".join(lines) + "\n"
        for item in visible:
            lines.extend([
                f"### {item.directive_id}",
                f"actor: {self._line(item.actor)}",
                f"task: {self._line(item.task)}",
                f"location: {self._line(item.location)}",
                f"status: {self._line(item.status)}",
                f"last processed tick: {self._line(item.last_processed_tick)}",
                f"ooc visibility: {self._line(item.metadata.get('ooc_visibility'))}",
                f"roleplay visibility: {self._line(item.metadata.get('visibility', 'hidden'))}",
                "",
            ])
        return "\n".join(lines)

    def _render_ticks(self, ticks: Iterable[dict[str, Any]]) -> str:
        lines = [
            TICKS_HEADING,
            "",
            "This register mirrors only explicitly safe teammate/background status. True surprises, enemy plans, unrevealed world events, and private tick detail remain in private runtime storage until normal play reveals them.",
            "",
        ]
        public = [item for tick in ticks if (item := self._public_tick(tick)) is not None]
        if not public:
            lines.append("No player-readable outside-player-perspective turns recorded.")
            return "\n".join(lines) + "\n"
        for record in public:
            position = record.get("position", {})
            lines.extend([
                f"### {record.get('tick_id', 'unknown-tick')}",
                f"day: {self._line(position.get('day'))}",
                f"phase: {self._line(position.get('phase'))}",
                "status: committed",
                "",
            ])
            self._render_actions(lines, record.get("actions", []))
            self._render_update_group(lines, "Automatic Updates", record.get("automatic_updates", []), "state")
            self._render_update_group(lines, "Resource Changes", record.get("resource_changes", []), "resource")
            self._render_world_updates(lines, record.get("world_updates", []))
            lines.extend(["", "#### Player Report", "", "status: not yet reported", ""])
        return "\n".join(lines)

    def _public_tick(self, record: Any) -> dict[str, Any] | None:
        if not isinstance(record, dict):
            return None
        filtered = {
            "tick_id": record.get("tick_id"),
            "position": record.get("position", {}),
            "actions": self._public_entries(record.get("actions")),
            "automatic_updates": self._public_entries(record.get("automatic_updates")),
            "resource_changes": self._public_entries(record.get("resource_changes")),
            "world_updates": self._public_entries(record.get("world_updates")),
        }
        return filtered if any(filtered[key] for key in ("actions", "automatic_updates", "resource_changes", "world_updates")) else None

    @staticmethod
    def _public_entries(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict) and str(item.get("ooc_visibility", "private")).casefold() in OOC_VISIBLE]

    @staticmethod
    def _directive_is_public(directive: BackgroundDirective) -> bool:
        return str(directive.metadata.get("ooc_visibility", "private")).casefold() in OOC_VISIBLE

    @staticmethod
    def _render_actions(lines: list[str], actions: list[dict[str, Any]]) -> None:
        lines.extend(["#### Off-Screen Actions"])
        if not actions:
            lines.append("- No player-readable off-screen actions.")
            return
        for action in actions:
            lines.extend([
                f"- actor: {BackgroundStateStore._line(action.get('actor'))}",
                f"  assigned task: {BackgroundStateStore._line(action.get('assigned_task'))}",
                f"  chosen action: {BackgroundStateStore._line(action.get('chosen_action', action.get('action')))}",
                f"  result: {BackgroundStateStore._line(action.get('result', action.get('status')))}",
                f"  ooc visibility: {BackgroundStateStore._line(action.get('ooc_visibility'))}",
                f"  roleplay visibility: {BackgroundStateStore._line(action.get('player_visibility', action.get('visibility', 'hidden')))}",
            ])

    @staticmethod
    def _render_update_group(lines: list[str], title: str, values: list[dict[str, Any]], label: str) -> None:
        lines.extend(["", f"#### {title}"])
        if not values:
            lines.append("- None.")
            return
        for item in values:
            name = item.get(label, item.get("state", item.get("resource", "update")))
            lines.append(
                f"- {label}: {name}; before: {item.get('before')}; delta: {item.get('delta')}; "
                f"after: {item.get('after')}; ooc visibility: {item.get('ooc_visibility')}; "
                f"roleplay visibility: {item.get('player_visibility', item.get('visibility', 'hidden'))}"
            )

    @staticmethod
    def _render_world_updates(lines: list[str], values: list[dict[str, Any]]) -> None:
        lines.extend(["", "#### World Updates"])
        if not values:
            lines.append("- None.")
            return
        for item in values:
            lines.append(
                f"- description: {BackgroundStateStore._line(item.get('description', item.get('summary')))}; "
                f"ooc visibility: {BackgroundStateStore._line(item.get('ooc_visibility'))}; "
                f"roleplay visibility: {BackgroundStateStore._line(item.get('player_visibility', item.get('visibility', 'hidden')))}"
            )

    def _replace_section_content(self, content: str, heading: str, section: str) -> str:
        match = re.search(rf"^{re.escape(heading)}\s*$", content, re.M)
        if match:
            next_heading = re.search(r"^##\s+", content[match.end():], re.M)
            end = match.end() + (next_heading.start() if next_heading else len(content[match.end():]))
            return content[:match.start()] + section.rstrip() + "\n\n" + content[end:]
        return content.rstrip() + ("\n\n" if content.strip() else "") + section.rstrip() + "\n"

    def _read_public(self) -> str:
        try:
            return self.register_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def _write_public(self, content: str) -> None:
        self.register_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.register_path.with_name(self.register_path.name + ".background-tmp")
        temporary.write_text(content.rstrip() + "\n", encoding="utf-8")
        self._replace_with_retry(temporary, self.register_path)

    @staticmethod
    def _replace_with_retry(temporary: Path, target: Path) -> None:
        for attempt in range(3):
            try:
                temporary.replace(target)
                return
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.05 * (attempt + 1))

    @staticmethod
    def _repo_root_for(register_path: Path) -> Path:
        # Normal production path is <repo>/markdown_files/Experimentation Register.md.
        return register_path.parent.parent if register_path.parent.name == "markdown_files" else Path.cwd()

    @staticmethod
    def _line(value: Any) -> str:
        return "none" if value is None else re.sub(r"\s+", " ", str(value)).strip()
