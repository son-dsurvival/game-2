"""Immutable, version-bound approval helpers for administrative proposals."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def proposal_digest(proposal: dict[str, Any]) -> str:
    """Digest reviewed content, excluding mutable approval bookkeeping."""
    value = {
        key: item
        for key, item in proposal.items()
        if key not in {"status", "approval", "proposal_digest"}
    }
    return _hash(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def bind_source_versions(proposal: dict[str, Any], *, repo_root: str | Path) -> dict[str, Any]:
    """Freeze every target's complete source image before player approval."""
    if not isinstance(proposal, dict):
        raise ValueError("Proposal must be an object")
    bound = copy.deepcopy(proposal)
    versions: dict[str, str] = {}
    for change in bound.get("changes", []):
        if not isinstance(change, dict) or not isinstance(change.get("target_file"), str):
            continue
        path = Path(repo_root).resolve() / change["target_file"]
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        versions[change["target_file"]] = _hash(content)
    bound["expected_source_hashes"] = versions
    bound["proposal_digest"] = proposal_digest(bound)
    return bound


def approve_proposal(proposal: dict[str, Any], *, approved_by: str = "player") -> dict[str, Any]:
    """Approve exactly the bound proposal; this never applies an edit."""
    if not isinstance(proposal, dict):
        raise ValueError("Proposal must be an object")
    if proposal.get("status") not in {"proposal_ready", "pending_approval"}:
        raise ValueError("Only a ready proposal can be approved")
    expected = proposal_digest(proposal)
    if proposal.get("proposal_digest") not in {None, expected}:
        raise ValueError("Proposal content changed after it was version-bound")
    approved = copy.deepcopy(proposal)
    approved["proposal_digest"] = expected
    approved["status"] = "approved"
    approved["approval"] = {
        "approved_by": approved_by,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "proposal_digest": expected,
    }
    return approved


def reject_proposal(proposal: dict[str, Any], *, rejected_by: str = "player", reason: str = "") -> dict[str, Any]:
    rejected = copy.deepcopy(proposal)
    rejected["status"] = "rejected"
    rejected["approval"] = {"rejected_by": rejected_by, "reason": reason}
    return rejected
