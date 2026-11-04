"""Readable branch-unlock registry used by routing and admin review."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

DEFAULT_BRANCHES = {
    "business": {"specialist": "business", "template": "business.md", "activation_tags": ["activity.business"]},
    "alchemy": {"specialist": "alchemy", "template": "alchemy.md", "activation_tags": ["activity.alchemy"]},
    "politics": {"specialist": "politics", "template": "politics.md", "activation_tags": ["activity.politics"]},
    "class": {"specialist": "class", "template": "class.md", "activation_tags": ["context.class_system"]},
    "relay": {"specialist": "relay", "template": "relay.md", "activation_tags": ["context.relay_system"]},
    "world": {"specialist": "world", "template": None, "activation_tags": ["activity.exploration"]},
    "consequences": {"specialist": "consequences", "template": None, "activation_tags": ["stakes.irreversible", "stakes.contested"]},
}


class BranchRegistry:
    """Read canonical branches plus pending session unlocks."""

    def __init__(
        self,
        repo_root: str | Path = ".",
        *,
        registry_path: str | Path = "markdown_files/Branch Registry.md",
        temp_memory_path: str | Path = "markdown_files/TEMP_MEMORY.md",
    ):
        root = Path(repo_root).resolve()
        self.registry_path = (root / registry_path).resolve()
        self.temp_memory_path = (root / temp_memory_path).resolve()

    def entries(self) -> dict[str, dict[str, Any]]:
        entries = {name: {**value, "branch": name, "status": "locked"} for name, value in DEFAULT_BRANCHES.items()}
        entries.update(self._parse(self._read(self.registry_path)))
        # Pending session decisions intentionally override canonical state until
        # day-end promotion. This makes a resolved unlock available next turn.
        entries.update(self._parse(self._read(self.temp_memory_path), pending_only=True))
        return entries

    def is_unlocked(self, specialist_name: str) -> bool:
        entry = self.entries().get(specialist_name)
        return bool(entry and str(entry.get("status", "locked")).casefold() == "unlocked")

    def unlocked_specialists(self) -> list[str]:
        return sorted(
            name for name, entry in self.entries().items()
            if str(entry.get("status", "locked")).casefold() == "unlocked"
        )

    def entry(self, branch: str) -> dict[str, Any] | None:
        return self.entries().get(branch)

    def specialists_for_tags(self, tags: set[str] | list[str]) -> list[str]:
        active_tags = set(tags)
        result = []
        for entry in self.entries().values():
            if str(entry.get("status", "locked")).casefold() != "unlocked":
                continue
            activation = entry.get("activation_tags", [])
            if isinstance(activation, str):
                activation = [activation]
            if set(str(tag) for tag in activation) & active_tags and entry.get("specialist"):
                result.append(str(entry["specialist"]))
        return sorted(set(result))

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    @staticmethod
    def _parse(content: str, *, pending_only: bool = False) -> dict[str, dict[str, Any]]:
        if pending_only:
            marker = "## Pending Branch Registry Updates"
            start = content.find(marker)
            if start < 0:
                return {}
            content = content[start:]
        result: dict[str, dict[str, Any]] = {}
        current: dict[str, Any] | None = None
        current_name: str | None = None
        for line in content.splitlines():
            heading = re.match(r"^##\s+(.+?)\s*$", line)
            if heading:
                name = heading.group(1).strip()
                if name.casefold() in {"branch registry", "pending branch registry updates"}:
                    continue
                current_name = re.sub(r"[^a-z0-9_ -]+", "", name.casefold()).strip().replace(" ", "_")
                current = {"branch": current_name}
                result[current_name] = current
                continue
            if current is None:
                continue
            field = re.match(r"^\s*([a-zA-Z][a-zA-Z0-9 _-]*):\s*(.*?)\s*$", line)
            if not field:
                continue
            key = re.sub(r"[^a-z0-9_]+", "_", field.group(1).casefold()).strip("_")
            value = field.group(2).strip()
            if key in {"activation_tags", "tags"}:
                current["activation_tags"] = [item.strip() for item in value.split(",") if item.strip()]
            else:
                current[key] = value
        return result
