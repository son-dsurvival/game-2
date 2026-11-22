"""Generate an incremental hierarchical Markdown evidence index.

Unchanged source files are reused from the prior index without being read. When
a file changes, only that file is parsed; section content hashes preserve model
descriptions for unaffected sections within it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from brain.state.evidence_ids import ID_RE, ensure_ids


HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")
SCHEMA_VERSION = 2


def slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return value or "section"


def clean_description(lines: list[str], fallback: str) -> str:
    for line in lines:
        text = line.strip()
        if not text or text.startswith("---") or text.startswith("```") or ID_RE.match(text):
            continue
        text = re.sub(r"^[-*•]\s+", "", text)
        text = re.sub(r"\s+", " ", text)
        if text:
            return text[:300]
    return fallback


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_signature(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"source_size": stat.st_size, "source_mtime_ns": stat.st_mtime_ns}


def build_file_node(path: Path, root: Path) -> dict[str, Any]:
    """Read one changed Markdown file and produce its index root."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    headings: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            heading = {
                "start": index,
                "level": len(match.group(1)),
                "name": match.group(2).strip().rstrip("#").strip(),
            }
            if index + 1 < len(lines):
                identifier = ID_RE.match(lines[index + 1].strip())
                if identifier:
                    heading["id"] = identifier.group(1)
            headings.append(heading)

    # Find the end of each section in one reverse pass rather than repeatedly
    # scanning all later headings.
    section_ends = [len(lines)] * len(headings)
    open_headings: list[int] = []
    for index, heading in enumerate(headings):
        while open_headings and heading["level"] <= headings[open_headings[-1]]["level"]:
            section_ends[open_headings.pop()] = heading["start"]
        open_headings.append(index)

    nodes: list[dict[str, Any]] = []
    stack: list[tuple[int, dict[str, Any]]] = []
    for position, heading in enumerate(headings):
        end = section_ends[position]
        next_heading_start = headings[position + 1]["start"] if position + 1 < len(headings) else end
        description = clean_description(
            lines[heading["start"] + 1:next_heading_start],
            f"Section covering {heading['name'].lower()}.",
        )
        section_text = "\n".join(lines[heading["start"]:end])
        node = {
            "id": heading.get("id"),
            "name": heading["name"],
            "description": description,
            "location": f"lines {heading['start'] + 1}-{end}",
            "content_hash": _hash_text(section_text),
            "under": [],
        }
        while stack and heading["level"] <= stack[-1][0]:
            stack.pop()
        if stack:
            stack[-1][1]["under"].append(node)
        else:
            nodes.append(node)
        stack.append((heading["level"], node))

    relative = path.relative_to(root).as_posix()
    first_heading = headings[0] if headings else None
    root_description = clean_description(
        lines[(first_heading["start"] + 1) if first_heading else 0:],
        f"Markdown source containing {path.stem.replace('_', ' ').lower()} information.",
    )
    return {
        "name": slug(path.stem),
        "description": root_description,
        "location": f"{root.name}/{relative}",
        "source_hash": _hash_text(content),
        "content_hash": _hash_text(content),
        **_file_signature(path),
        "under": nodes,
    }


def _collect_descriptions(
    node: dict[str, Any], source_location: str, path: tuple[str, ...], result: dict[tuple[str, tuple[str, ...]], dict[str, Any]], by_id: dict[str, dict[str, Any]] | None = None
) -> None:
    if not source_location:
        source_location = str(node.get("location", ""))
    result[(source_location, path)] = node
    if by_id is not None and isinstance(node.get("id"), str):
        by_id[str(node["id"])] = node
    for child in node.get("under", []):
        if isinstance(child, dict):
            _collect_descriptions(child, source_location, (*path, str(child.get("name", ""))), result, by_id)


def _preserve_descriptions(
    node: dict[str, Any], source_location: str, path: tuple[str, ...], previous: dict[tuple[str, tuple[str, ...]], dict[str, Any]], previous_by_id: dict[str, dict[str, Any]] | None = None
) -> None:
    if not source_location:
        source_location = str(node.get("location", ""))
    prior = None
    identifier = node.get("id")
    if previous_by_id and isinstance(identifier, str):
        prior = previous_by_id.get(identifier)
        # A renamed section keeps its identity but needs a new description.
        if prior and prior.get("name") != node.get("name"):
            prior = None
    if prior is None:
        prior = previous.get((source_location, path))
    # Preserve descriptions across line shifts, body edits, and re-parenting
    # when the stable identity and name still match. Renames are re-described.
    if prior and prior.get("description_source") == "deepseek":
        node["description"] = prior["description"]
        node["description_source"] = "deepseek"
        if prior.get("description_model"):
            node["description_model"] = prior["description_model"]
    for child in node.get("under", []):
        if isinstance(child, dict):
            _preserve_descriptions(child, source_location, (*path, str(child.get("name", ""))), previous, previous_by_id)


def _previous_roots(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(node.get("location")): node
        for node in index.get("under", [])
        if isinstance(node, dict) and isinstance(node.get("location"), str)
    }


def _is_unchanged(path: Path, root: Path, prior: dict[str, Any] | None) -> bool:
    if not prior or "source_mtime_ns" not in prior or "source_size" not in prior:
        return False
    if prior.get("location") != f"{root.name}/{path.relative_to(root).as_posix()}":
        return False
    signature = _file_signature(path)
    return all(prior.get(key) == value for key, value in signature.items())


def build_index(source_root: Path, previous_index: dict[str, Any] | None = None, *, force: bool = False, ensure_section_ids: bool = False) -> dict[str, Any]:
    """Build an index, reading only added or changed Markdown files."""
    if ensure_section_ids:
        ensure_ids(source_root)
    previous_index = previous_index if isinstance(previous_index, dict) else {}
    roots = _previous_roots(previous_index) if previous_index.get("schema_version") == SCHEMA_VERSION else {}
    previous_descriptions: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    previous_by_id: dict[str, dict[str, Any]] = {}
    for root in roots.values():
        _collect_descriptions(root, "", (str(root.get("name", "")),), previous_descriptions, previous_by_id)

    entries: list[dict[str, Any]] = []
    for path in sorted(source_root.rglob("*.md")):
        location = f"{source_root.name}/{path.relative_to(source_root).as_posix()}"
        prior = roots.get(location)
        if not force and _is_unchanged(path, source_root, prior):
            entries.append(prior)
            continue
        node = build_file_node(path, source_root)
        _preserve_descriptions(node, "", (str(node["name"]),), previous_descriptions, previous_by_id)
        entries.append(node)
    return {
        "schema_version": SCHEMA_VERSION,
        "name": "campaign_evidence_index",
        "description": "Hierarchical map of campaign Markdown sources and their headings.",
        "location": source_root.name,
        "under": entries,
    }


def _flatten_heading_nodes(index: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    def walk(node: dict[str, Any], path: tuple[str, ...], source: str) -> None:
        current_source = source or str(node.get("location", ""))
        current_path = (*path, str(node.get("name", "")))
        if isinstance(node.get("id"), str) and str(node.get("location", "")).startswith("lines "):
            nodes.append({
                "id": str(node["id"]),
                "name": str(node.get("name", "")),
                "source": current_source,
                "path": current_path,
                "location": str(node.get("location", "")),
            })
        for child in node.get("under", []):
            if isinstance(child, dict):
                walk(child, current_path, current_source)

    for root in index.get("under", []):
        if isinstance(root, dict):
            walk(root, (), "")
    return nodes


def description_targets(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[str]:
    """Return stable IDs for new or renamed sections only."""
    old_nodes = _flatten_heading_nodes(previous or {})
    old_by_id = {item["id"]: item for item in old_nodes}
    old_by_location_path = {
        (item["source"], item["path"]): item for item in old_nodes
    }
    targets: list[str] = []
    for item in _flatten_heading_nodes(current):
        prior = old_by_id.get(item["id"])
        if prior is None:
            legacy = old_by_location_path.get((item["source"], item["path"]))
            if legacy is not None and legacy.get("name") == item.get("name"):
                continue
            targets.append(item["id"])
        elif prior.get("name") != item.get("name"):
            targets.append(item["id"])
    return targets


def write_index(path: Path, index: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Incrementally index campaign Markdown")
    parser.add_argument("--force", action="store_true", help="Rebuild every Markdown file")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    source_root = repo_root / "markdown_files"
    output = repo_root / "brain" / "info" / "evidence_index.json"
    try:
        previous = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    index = build_index(source_root, previous, force=args.force, ensure_section_ids=True)
    write_index(output, index)
    print(f"Indexed {len(index['under'])} Markdown files incrementally: {output}")


if __name__ == "__main__":
    main()
