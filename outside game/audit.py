"""Append-only audit records for administrative operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()

    def append(self, entry: dict[str, Any]) -> dict[str, Any]:
        value = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **entry,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        return value
