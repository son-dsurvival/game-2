"""Build a heading/line index for campaign Markdown sections.

The recorder uses this index to place pending canon by target Markdown file and
exact heading instead of treating a whole file as one undifferentiated blob.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def build_index(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root).resolve()
    files: dict[str, Any] = {}
    for path in sorted((root / "markdown_files").glob("*.md"), key=lambda p: p.name.casefold()):
        lines = path.read_text(encoding="utf-8").splitlines()
        headings: list[dict[str, Any]] = []
        stack: list[tuple[int, str]] = []
        for number, line in enumerate(lines, start=1):
            match = HEADING_RE.match(line)
            if not match:
                continue
            level = len(match.group(1))
            heading = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent_path = [item[1] for item in stack]
            headings.append(
                {
                    "heading": heading,
                    "level": level,
                    "line_start": number,
                    "line_end": len(lines),
                    "parent_path": parent_path,
                    "heading_path": parent_path + [heading],
                }
            )
            stack.append((level, heading))
        for index, item in enumerate(headings):
            next_start = headings[index + 1]["line_start"] if index + 1 < len(headings) else len(lines) + 1
            item["line_end"] = next_start - 1
            item["section_id"] = f"{path.relative_to(root).as_posix()}::{ ' > '.join(item['heading_path']) }"
        relative = path.relative_to(root).as_posix()
        files[relative] = {
            "path": relative,
            "line_count": len(lines),
            "sections": headings,
        }
    return {"version": 1, "source_root": "markdown_files", "files": files}


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Markdown files by heading")
    parser.add_argument("--output", default="brain/info/canon_section_index.json")
    args = parser.parse_args()
    index = build_index(".")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(index["files"]), "sections": sum(len(v["sections"]) for v in index["files"].values()), "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
