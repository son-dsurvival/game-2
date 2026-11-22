"""Stable evidence IDs embedded in campaign Markdown headings."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

ID_RE = re.compile(r"^\s*<!--\s*evidence-id:\s*([A-Za-z0-9._:-]+)\s*-->\s*$")
HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")


def slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return value or "section"


def _line_text(line: str) -> str:
    return line.rstrip("\r\n")


def _line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return "\n"


def _heading_name(line: str) -> str | None:
    match = HEADING_RE.match(_line_text(line))
    return match.group(2).strip().rstrip("#").strip() if match else None


def _existing_ids(path: Path) -> list[str]:
    ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ID_RE.match(line)
        if match:
            ids.append(match.group(1))
    return ids


def _candidate_id(file_stem: str, heading_path: list[str], used: set[str]) -> str:
    base = ".".join([slug(file_stem), *(slug(item) for item in heading_path)])
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}.{suffix}"
        suffix += 1
    return candidate


def ensure_ids(source_root: str | Path) -> list[Path]:
    """Insert stable IDs below headings that do not already have one.

    Existing IDs are never changed. The returned paths are the Markdown files
    that were modified. Duplicate existing IDs fail closed rather than silently
    breaking evidence identity.
    """
    root = Path(source_root).resolve()
    paths = sorted(root.rglob("*.md"))
    used: set[str] = set()
    for path in paths:
        for identifier in _existing_ids(path):
            if identifier in used:
                raise ValueError(f"Duplicate evidence ID {identifier!r} in {path}")
            used.add(identifier)

    changed: list[Path] = []
    for path in paths:
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines(keepends=True)
        output: list[str] = []
        heading_stack: list[tuple[int, str]] = []
        index = 0
        file_changed = False
        while index < len(lines):
            line = lines[index]
            output.append(line)
            match = HEADING_RE.match(_line_text(line))
            if not match:
                index += 1
                continue
            level = len(match.group(1))
            name = match.group(2).strip().rstrip("#").strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, name))
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            if ID_RE.match(_line_text(next_line)):
                index += 1
                continue
            identifier = _candidate_id(path.stem, [item[1] for item in heading_stack], used)
            used.add(identifier)
            output.append(f"<!-- evidence-id: {identifier} -->{_line_ending(line)}")
            file_changed = True
            index += 1
        if file_changed:
            with path.open("w", encoding="utf-8", newline="") as handle:
                handle.write("".join(output))
            changed.append(path)
    return changed


def node_id(node: dict[str, Any]) -> str | None:
    value = node.get("id")
    return str(value) if isinstance(value, str) and value.strip() else None
