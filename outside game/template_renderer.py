"""Render readable Markdown documents from administrative templates."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


TEMPLATE_TARGETS = {
    "status sheet.md": "character_status",
    "character relationship.md": "character_relationship",
    "Ledger Resources.md": "ledger_resources",
    "Experimentation Register.md": "experimentation_register",
    "🌍 CORE WORLD FRAME (REFINED).md": "core_world_frame",
    "Branch Registry.md": "branch_registry",
}
BLOCK_TEMPLATES = {
    "stats_modifiers": "stats_modifier",
    "class_modifiers": "class_modifier",
    "effect_modifiers": "effect_modifier",
    "active_skills": "active_skill",
    "equipment": "equipment",
    "party_relationship_blocks": "relationship_party_block",
    "non_party_relationship_blocks": "relationship_non_party_block",
}


class TemplateRenderer:
    def __init__(self, template_root: str | Path):
        self.root = Path(template_root).resolve()

    def template_for_target(self, target_file: str) -> str | None:
        return TEMPLATE_TARGETS.get(Path(target_file).name)

    def render(self, template_name: str, values: dict[str, Any]) -> str:
        content = self._read(template_name)
        content = self._render_blocks(content, values)
        content = self._replace_scalar_tokens(content, values)
        content = self._fill_labeled_fields(content, values)
        content = re.sub(r"\n{3,}", "\n\n", content).strip() + "\n"
        self.validate(content, template_name, require_no_directives=True)
        return content

    def validate(self, content: str, template_name: str, *, require_no_directives: bool = True) -> None:
        if "```json" in content.casefold():
            raise ValueError("Campaign Markdown must remain human-readable; JSON blocks are not allowed")
        if require_no_directives and re.search(r"\{check [^}]+\}|\{(?:party|non-party) relationship blocks\}", content, re.I):
            raise ValueError("Unrendered template directive remains in the document")
        unresolved = sorted(set(re.findall(r"\{[^{}\n]+\}", content)))
        if unresolved:
            raise ValueError(f"Unresolved template values remain: {', '.join(unresolved[:8])}")
        template = self._read(template_name)
        required_headings = {
            self._heading_key(line)
            for line in template.splitlines()
            if line.lstrip().startswith("#") and "{" not in line
        }
        actual_headings = {
            self._heading_key(line)
            for line in content.splitlines()
            if line.lstrip().startswith("#")
        }
        missing = sorted(required_headings - actual_headings)
        if missing:
            raise ValueError(f"Document is missing template headings: {', '.join(missing)}")

    def _render_blocks(self, content: str, values: dict[str, Any]) -> str:
        for key, template_name in BLOCK_TEMPLATES.items():
            token_names = {
                key,
                key.replace("_", " "),
                f"check {template_name.replace('_', ' ')} template",
            }
            if key == "active_skills":
                token_names.add("check active skills template")
            if key == "equipment":
                token_names.add("check equipment modifier template")
            if key == "non_party_relationship_blocks":
                token_names.add("non-party relationship blocks")
            pattern = "|".join(re.escape(name) for name in token_names)
            entries = values.get(key, [])
            if key == "stats_modifiers" and isinstance(entries, dict):
                # A status sheet has one modifier list under each stat heading.
                for stat, stat_entries in entries.items():
                    heading_pattern = rf"(####\s+{re.escape(str(stat))}\s*:\s*\n)\{{check stats modifier template\}}"
                    replacement = rf"\1{self._render_entries(template_name, stat_entries)}"
                    content = re.sub(heading_pattern, replacement, content, flags=re.I)
                content = re.sub(r"\{check stats modifier template\}", "No modifiers recorded.\n", content, flags=re.I)
                continue
            replacement = self._render_entries(template_name, entries)
            content = re.sub(rf"\{{(?:{pattern})\}}", lambda _match: replacement, content, flags=re.I)
        return content

    def _render_entries(self, template_name: str, entries: Any) -> str:
        if not isinstance(entries, list) or not entries:
            return "No entries recorded.\n"
        rendered = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            block = self._read(template_name)
            block = self._replace_scalar_tokens(block, item)
            block = self._fill_labeled_fields(block, item)
            rendered.append(block.strip())
        return "\n\n".join(rendered) + "\n" if rendered else "No entries recorded.\n"

    @staticmethod
    def _replace_scalar_tokens(content: str, values: dict[str, Any]) -> str:
        for key, value in values.items():
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                token = "{" + str(key) + "}"
                content = content.replace(token, str(value))
        return content

    @staticmethod
    def _fill_labeled_fields(content: str, values: dict[str, Any]) -> str:
        normalized = {
            re.sub(r"[^a-z0-9]+", " ", str(key).casefold()).strip(): value
            for key, value in values.items()
            if isinstance(value, (str, int, float)) and not isinstance(value, bool)
        }
        lines = []
        for line in content.splitlines():
            match = re.match(r"^(\s*)([^:#\n]+):(\s*)(.*)$", line)
            if match:
                label = re.sub(r"[^a-z0-9]+", " ", match.group(2).casefold()).strip()
                if label in normalized:
                    line = f"{match.group(1)}{match.group(2)}: {normalized[label]}"
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _heading_key(line: str) -> str:
        return re.sub(r"\s+", " ", line.lstrip().casefold()).strip()

    def _read(self, template_name: str) -> str:
        path = self.root / f"{template_name}.md"
        if not path.is_file():
            raise FileNotFoundError(f"Unknown administrative template: {template_name}")
        return path.read_text(encoding="utf-8")
