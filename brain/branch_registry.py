"""Readable branch-unlock registry used by routing and admin review."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from brain.persistence import atomic_text

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

    def record_candidates(self, candidates: list[dict[str, Any]]) -> list[str]:
        """Persist discovered branches as readable ``candidate`` entries.

        Candidate storage is intentionally not activation: routing methods below
        continue to require ``status: unlocked``. Existing unlocked branches are
        never downgraded by discovery.
        """
        if not isinstance(candidates, list) or not candidates:
            return []
        try:
            content = self.registry_path.read_text(encoding="utf-8")
        except OSError:
            content = "# Branch Registry\n\n"
        changed: list[str] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            branch = re.sub(r"[^a-z0-9_]+", "_", str(item.get("branch", "")).casefold()).strip("_")
            specialist = re.sub(r"[^a-z0-9_]+", "_", str(item.get("specialist", branch)).casefold()).strip("_")
            if not branch or not specialist:
                continue
            existing = self.entry(branch)
            if existing and str(existing.get("status", "locked")).casefold() == "unlocked":
                continue
            tags = item.get("activation_tags", [])
            if isinstance(tags, str):
                tags = [tags]
            tags_text = ", ".join(str(tag).strip() for tag in tags if str(tag).strip()) or "none"
            signals = item.get("signals", [])
            sources = []
            if isinstance(signals, list):
                sources = list(dict.fromkeys(
                    str(signal.get("source")) for signal in signals
                    if isinstance(signal, dict) and signal.get("source")
                ))
            reason = str(item.get("description") or "Identified by branch discovery.").replace("\n", " ").strip()
            discovery_status = str(item.get("status", "candidate"))
            default = DEFAULT_BRANCHES.get(branch, {})
            existing_template = (existing or {}).get("template")
            if str(existing_template).casefold() in {"", "none", "null"}:
                existing_template = None
            template = item.get("template") or existing_template or default.get("template") or "none"
            block = "\n".join([
                f"## {branch.replace('_', ' ').title()}",
                "status: candidate",
                f"specialist: {specialist}",
                f"template: {str(template)}",
                f"activation tags: {tags_text}",
                f"discovery status: {discovery_status}",
                f"discovery sources: {', '.join(sources) or 'runtime evidence'}",
                f"reason: {reason}",
                "",
            ]) + "\n"
            title = branch.replace("_", " ").title()
            match = re.search(rf"^##\s+{re.escape(title)}\s*$", content, re.M | re.I)
            if match:
                next_heading = re.search(r"^##\s+", content[match.end():], re.M)
                end = match.end() + (next_heading.start() if next_heading else len(content[match.end():]))
                old_block = content[match.start():end]
                if old_block != block:
                    content = content[:match.start()] + block + content[end:]
                    changed.append(branch)
            else:
                unlock_rules = re.search(r"^##\s+Unlock Rules\s*$", content, re.M | re.I)
                if unlock_rules:
                    content = content[:unlock_rules.start()] + block + "\n" + content[unlock_rules.start():]
                else:
                    content = content.rstrip() + "\n\n" + block
                changed.append(branch)
        if changed:
            atomic_text(self.registry_path, content.rstrip() + "\n")
        return changed

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
            if key in {"activation_tags", "tags", "sections"}:
                current[key if key != "tags" else "activation_tags"] = [item.strip() for item in value.split(",") if item.strip()]
            elif key in {"questions", "evidence_requirements"}:
                current[key] = [item.strip() for item in value.split("|") if item.strip()]
            else:
                current[key] = value
        return result
