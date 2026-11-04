"""Use DeepSeek to enrich the hierarchical evidence index descriptions.

Python remains authoritative for file locations, hierarchy, and line ranges. The
model only writes short factual descriptions for indexed nodes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    from brain.model_gateway import ModelGateway
except ModuleNotFoundError:  # Direct execution: python brain/describe_evidence_index.py
    from model_gateway import ModelGateway


SYSTEM_PROMPT = """You describe a hierarchical Markdown evidence index.

Return JSON only in this shape:
{"descriptions": [{"id": "...", "description": "..."}]}

For every supplied node, write one concise factual description in one sentence.
Use only the node name, its parent path, and the supplied source excerpt. Do not
invent rules, outcomes, characters, numbers, or mechanics. Do not decide whether
evidence is relevant. If the excerpt is sparse, describe the section's subject
conservatively from its heading. Preserve the supplied IDs exactly.
"""


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def parse_line_range(location: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"lines\s+(\d+)-(\d+)", location.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def source_path(repo_root: Path, location: str) -> Path:
    prefix = "markdown_files/"
    relative = location[len(prefix):] if location.startswith(prefix) else location
    return repo_root / "markdown_files" / relative


def node_excerpt(
    repo_root: Path,
    node: dict[str, Any],
    source_lines: dict[Path, list[str]],
) -> str:
    path = source_path(repo_root, node["source_location"])
    if path not in source_lines:
        try:
            source_lines[path] = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            source_lines[path] = []
    lines = source_lines[path]
    if not lines:
        return "[source file is missing or empty]"
    line_range = parse_line_range(node["location"])
    if line_range:
        start, end = line_range
        excerpt = "\n".join(lines[max(0, start - 1):end])
    else:
        excerpt = "\n".join(lines[:80])
    return excerpt[:2400]


def flatten_index(index: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    """Flatten the index while reading each source file at most once."""
    flattened: list[dict[str, Any]] = []
    source_lines: dict[Path, list[str]] = {}

    def walk(node: dict[str, Any], path: list[str], source_location: str) -> None:
        current_path = [*path, node["name"]]
        if source_location == "":
            source_location = node["location"]
        flattened.append({
            "id": str(len(flattened)),
            "path": current_path,
            "source_location": source_location,
            "location": node["location"],
            "current_description": node.get("description", ""),
            "excerpt": node_excerpt(
                repo_root,
                {**node, "source_location": source_location},
                source_lines,
            ),
            "node": node,
        })
        for child in node.get("under", []):
            walk(child, current_path, source_location)

    for root in index.get("under", []):
        walk(root, [], "")
    return flattened


def request_descriptions(gateway: ModelGateway, model: str, batch: list[dict[str, Any]]) -> dict[str, str]:
    payload = [
        {
            "id": item["id"],
            "path": item["path"],
            "location": item["location"],
            "current_description": item["current_description"],
            "source_excerpt": item["excerpt"],
        }
        for item in batch
    ]
    content = gateway.complete(
        stage="evidence.description",
        model=model,
        json_mode=True,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    ).content
    if not content:
        raise RuntimeError("DeepSeek returned an empty description response")
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("DeepSeek returned invalid description JSON") from exc

    raw_descriptions = result.get("descriptions")
    if not isinstance(raw_descriptions, list):
        raise RuntimeError("DeepSeek description response is missing descriptions")
    expected = {item["id"] for item in batch}
    descriptions: dict[str, str] = {}
    for item in raw_descriptions:
        if not isinstance(item, dict):
            raise RuntimeError("DeepSeek returned a malformed description")
        identifier = str(item.get("id", ""))
        description = item.get("description")
        if identifier not in expected:
            raise RuntimeError(f"DeepSeek returned an unknown description ID: {identifier}")
        if not isinstance(description, str) or not description.strip():
            raise RuntimeError(f"DeepSeek returned an empty description for ID: {identifier}")
        descriptions[identifier] = description.strip()
    if set(descriptions) != expected:
        missing = sorted(expected - set(descriptions))
        raise RuntimeError(f"DeepSeek omitted descriptions: {missing}")
    return descriptions


def write_index(path: Path, index: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Describe evidence-index nodes with DeepSeek")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--force", action="store_true", help="Regenerate existing DeepSeek descriptions")
    parser.add_argument("--max-nodes", type=int, help="Describe only the first N nodes")
    args = parser.parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")

    load_dotenv_if_available()
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY")
    if not api_key:
        raise SystemExit("Set DEEPSEEK_API_KEY or API_KEY in the existing .env file")

    repo_root = Path(__file__).resolve().parent.parent
    index_path = repo_root / "brain" / "info" / "evidence_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    nodes = flatten_index(index, repo_root)
    if args.max_nodes is not None:
        nodes = nodes[:args.max_nodes]

    pending = [
        item
        for item in nodes
        if args.force or item["node"].get("description_source") != "deepseek"
    ]
    if not pending:
        print("Evidence index already has DeepSeek descriptions.")
        return

    gateway = ModelGateway(repo_root)
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    total = len(pending)
    for offset in range(0, total, args.batch_size):
        batch = pending[offset:offset + args.batch_size]
        descriptions = request_descriptions(gateway, model, batch)
        for item in batch:
            node = item["node"]
            node["description"] = descriptions[item["id"]]
            node["description_source"] = "deepseek"
            node["description_model"] = model
        write_index(index_path, index)
        print(f"Described {min(offset + len(batch), total)}/{total} nodes")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"Completed DeepSeek descriptions: {total}")


if __name__ == "__main__":
    main()
