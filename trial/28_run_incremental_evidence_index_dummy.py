"""Verify incremental evidence indexing without provider calls."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brain.build_evidence_index import build_index


def node_by_name(nodes: list[dict], name: str) -> dict:
    return next(node for node in nodes if node["name"] == name)


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        markdown_root = Path(temporary) / "markdown_files"
        markdown_root.mkdir()
        unchanged = markdown_root / "unchanged.md"
        changed = markdown_root / "changed.md"
        unchanged.write_text("# Unchanged\n\n## Stable\nSame text.\n", encoding="utf-8")
        changed.write_text(
            "# Changed\n\n## Preserved Section\nSame text.\n\n## Rebuilt Section\nBefore.\n",
            encoding="utf-8",
        )
        first = build_index(markdown_root)
        changed_root = node_by_name(first["under"], "changed")
        changed_document = changed_root["under"][0]
        preserved = node_by_name(changed_document["under"], "Preserved Section")
        rebuilt = node_by_name(changed_document["under"], "Rebuilt Section")
        preserved.update(description="Model description that should survive.", description_source="deepseek", description_model="fake")
        rebuilt.update(description="Model description that must be refreshed.", description_source="deepseek", description_model="fake")

        # Ensure the filesystem records a changed signature even on filesystems
        # with coarse timestamp behavior.
        time.sleep(0.02)
        changed.write_text(
            "# Changed\n\n## Preserved Section\nSame text.\n\n## Rebuilt Section\nAfter.\n",
            encoding="utf-8",
        )
        second = build_index(markdown_root, first)
        unchanged_first = node_by_name(first["under"], "unchanged")
        unchanged_second = node_by_name(second["under"], "unchanged")
        changed_second = node_by_name(second["under"], "changed")["under"][0]
        preserved_second = node_by_name(changed_second["under"], "Preserved Section")
        rebuilt_second = node_by_name(changed_second["under"], "Rebuilt Section")

        assertions = {
            "schema_version": second["schema_version"] == 2,
            "unchanged_file_reused": unchanged_first is unchanged_second,
            "unchanged_section_description_preserved": preserved_second.get("description") == "Model description that should survive.",
            "changed_section_description_invalidated": rebuilt_second.get("description") != "Model description that must be refreshed." and "description_source" not in rebuilt_second,
        }
        if not all(assertions.values()):
            raise AssertionError(assertions)
        result = {"status": "passed", **assertions}
        (ROOT / "trial" / "28_incremental_evidence_index_result.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
