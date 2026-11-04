"""Apply immutable, approved Markdown proposals as recoverable transactions."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from approval import proposal_digest
from brain.persistence import atomic_json, atomic_text
from audit import AuditLog
from template_renderer import TemplateRenderer


class AdminEditor:
    """Deterministic editor: compose per-file changes, then commit all or restore."""

    # Lore files hold player-authored world content whose headings legitimately
    # diverge from the starting template; edits are exact-text checked only.
    LORE_FILES = {'🌍 CORE WORLD FRAME (REFINED).md'}

    def __init__(self, repo_root: str | Path = "."):
        self.root = Path(repo_root).resolve()
        self.audit = AuditLog(self.root / "outside game" / "audit" / "admin_operations.jsonl")
        self.templates = TemplateRenderer(self.root / "outside game" / "templates")
        self.transactions = self.root / "brain" / "state" / "editor_transactions"
        self.receipts = self.root / "brain" / "state" / "editor_receipts"

    def apply(self, proposal: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
        error = self._verify_approval(proposal)
        if error:
            return {"status": "rejected", "reason": error}
        proposal_id = str(proposal.get("proposal_id") or proposal.get("request_id") or proposal.get("proposal_digest"))
        receipt_path = self.receipts / f"{self._safe_id(proposal_id)}.json"
        if receipt_path.is_file():
            receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
            if receipt.get('proposal_digest') != proposal['proposal_digest']:
                return {'status': 'rejected', 'reason': 'Proposal identity already belongs to different content.'}
            return receipt
        changes = proposal.get("changes", [])
        if not isinstance(changes, list) or not changes:
            return {"status": "rejected", "reason": "Approved proposal contains no changes."}

        prepared, errors = self._compose(changes, proposal.get("expected_source_hashes", {}))
        if errors:
            self.audit.append({"request_id": proposal.get("request_id"), "operation": "apply_admin_proposal", "status": "rejected", "errors": errors})
            return {"status": "rejected", "errors": errors}
        if dry_run:
            return {"status": "dry_run", "request_id": proposal.get("request_id"), "changes": [self._public_change(item) for item in prepared]}

        transaction = self._stage(proposal_id, prepared)
        try:
            for item in prepared:
                item["path"].parent.mkdir(parents=True, exist_ok=True)
                item["staged"].replace(item["path"])
            result = {
                "status": "applied",
                "request_id": proposal.get("request_id"),
                "proposal_id": proposal_id,
                "proposal_digest": proposal["proposal_digest"],
                "files_changed": [item["target_file"] for item in prepared],
                "changes": [self._public_change(item) for item in prepared],
            }
            self.audit.append({
                'request_id': proposal.get('request_id'), 'operation': 'apply_admin_proposal', 'status': 'applied',
                'proposal_digest': proposal['proposal_digest'], 'approved_by': proposal['approval'].get('approved_by'),
                'files_changed': result['files_changed'], 'changes': result['changes'],
            })
            # This durable receipt is the commit point. Recovery keeps its files.
            self._write_json_atomic(receipt_path, result)
        except Exception:
            self._restore_transaction(transaction)
            shutil.rmtree(transaction)
            return {'status': 'rejected', 'reason': 'Transaction rolled back; approved proposal retained for retry.'}
        shutil.rmtree(transaction, ignore_errors=True)
        return result

    def recover(self) -> list[dict[str, Any]]:
        """Restore any transaction left staged by a crash before its receipt."""
        results: list[dict[str, Any]] = []
        if not self.transactions.is_dir():
            return results
        for transaction in self.transactions.iterdir():
            manifest = transaction / "manifest.json"
            if not manifest.is_file() or (transaction / "receipt.json").is_file():
                continue
            data = json.loads(manifest.read_text(encoding="utf-8"))
            receipt = self.receipts / f"{self._safe_id(data.get('proposal_id', ''))}.json"
            committed = receipt.is_file()
            if not committed:
                self._restore_transaction(transaction)
            results.append({'transaction': transaction.name, 'status': 'committed' if committed else 'rolled_back', 'files': [item['target_file'] for item in data.get('files', [])]})
            shutil.rmtree(transaction, ignore_errors=True)
        return results

    def _verify_approval(self, proposal: Any) -> str | None:
        if not isinstance(proposal, dict) or proposal.get("status") != "approved":
            return "Proposal has not been approved."
        digest = proposal.get("proposal_digest")
        if not isinstance(digest, str) or digest != proposal_digest(proposal):
            return "Approval digest does not match proposal content."
        approval = proposal.get("approval")
        if not isinstance(approval, dict) or approval.get("proposal_digest") != digest:
            return "Approval is not bound to this proposal digest."
        if not isinstance(proposal.get("expected_source_hashes"), dict):
            return "Proposal has no bound source versions."
        return None

    def _compose(self, changes: list[Any], expected: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        expected = expected if isinstance(expected, dict) else {}
        groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        errors: list[dict[str, Any]] = []
        for index, change in enumerate(changes):
            if not isinstance(change, dict) or not isinstance(change.get("target_file"), str):
                errors.append({"error": f"change_{index} is malformed"})
                continue
            groups.setdefault(change["target_file"], []).append((index, change))
        prepared = []
        for target, items in groups.items():
            path, path_error = self._target_path(target)
            if path_error:
                errors.append({"error": path_error, "target_file": target})
                continue
            original = path.read_text(encoding="utf-8") if path.exists() else ""
            actual_hash = self._hash(original)
            if expected.get(target) != actual_hash:
                errors.append({"error": "source version changed since approval", "target_file": target, "expected": expected.get(target), "actual": actual_hash})
                continue
            current, exists = original, path.exists()
            final_meta: dict[str, Any] | None = None
            for index, change in items:
                result = self._apply_change(change, index, target, path, current, exists)
                if "error" in result:
                    errors.append(result)
                    break
                current, exists, final_meta = result["updated"], True, result
            if final_meta:
                prepared.append({
                    "path": path, "target_file": target, "updated": current, "original": original,
                    "before_hash": actual_hash, "after_hash": self._hash(current),
                    "template": final_meta.get("template"), "action": "+".join(item[1].get("action", "") for item in items),
                    "reason": "; ".join(str(item[1].get("reason", "")) for item in items if item[1].get("reason")),
                })
        return prepared, errors

    def _apply_change(self, change: dict[str, Any], index: int, target: str, path: Path, current: str, exists: bool) -> dict[str, Any]:
        action = change.get("action")
        if action not in {"create", "fill", "update", "delete"}:
            return {"error": f"change_{index} has an invalid action"}
        old, new = change.get("old_text", ""), change.get("new_text", "")
        if not isinstance(old, str) or not isinstance(new, str):
            return {"error": f"change_{index} old_text/new_text must be strings"}
        template = change.get("template") or self.templates.template_for_target(target)
        values = change.get("values") if isinstance(change.get("values"), dict) else {}
        campaign = target.startswith("markdown_files/")
        try:
            if action == "create":
                if exists:
                    return {"error": f"change_{index} cannot create an existing file"}
                if target.startswith("outside game/templates/"):
                    updated = new
                elif template:
                    updated = self.templates.render(template, values) if values or not new else new
                    self.templates.validate(updated, template)
                else:
                    return {"error": f"change_{index} creation requires a template"}
            elif action == "fill" and not current.strip():
                if not template:
                    return {"error": f"change_{index} fill requires a template"}
                updated = self.templates.render(template, values)
            else:
                if not exists or not old or current.count(old) != 1:
                    return {"error": f"change_{index} old_text did not match exactly once", "target_file": target, "matches": current.count(old)}
                updated = current.replace(old, new, 1)
                if template and campaign and path.name not in self.LORE_FILES:
                    removed = self._headings(current) - self._headings(updated)
                    if removed:
                        return {"error": f"change_{index} would remove existing headings", "target_file": target, "removed": sorted(removed)[:6]}
        except (FileNotFoundError, ValueError) as exc:
            return {"error": f"change_{index} template validation failed: {exc}", "target_file": target}
        if "```json" in updated.casefold():
            return {"error": f"change_{index} would write a JSON blob into Markdown"}
        return {"updated": updated, "template": template}

    @staticmethod
    def _headings(text: str) -> set[str]:
        return {line.strip() for line in text.splitlines() if line.lstrip().startswith('#')}

    def _stage(self, proposal_id: str, prepared: list[dict[str, Any]]) -> Path:
        transaction = self.transactions / f"txn-{self._safe_id(proposal_id)}-{uuid.uuid4().hex[:8]}"
        transaction.mkdir(parents=True, exist_ok=False)
        files = []
        for index, item in enumerate(prepared):
            original = transaction / f"{index}.original"
            staged = transaction / f"{index}.staged"
            original.write_text(item["original"], encoding="utf-8")
            staged.write_text(item["updated"], encoding="utf-8")
            item["staged"] = staged
            files.append({"target_file": item["target_file"], "original": original.name, "existed": item["path"].exists()})
        self._write_json_atomic(transaction / "manifest.json", {'files': files, 'proposal_id': proposal_id})
        return transaction

    def _restore_transaction(self, transaction: Path) -> None:
        manifest = json.loads((transaction / 'manifest.json').read_text(encoding='utf-8'))
        for item in manifest['files']:
            target, error = self._target_path(item['target_file'])
            if error:
                raise RuntimeError('Invalid recovery target.')
            if item['existed']:
                # Keep backups until the entire recovery succeeds, including a
                # process crash while recovering an earlier process crash.
                atomic_text(target, (transaction / item['original']).read_text(encoding='utf-8'))
            else:
                target.unlink(missing_ok=True)

    def _target_path(self, target: str) -> tuple[Path, str | None]:
        campaign = target.startswith("markdown_files/")
        templates = target.startswith("outside game/templates/")
        if not target.endswith(".md") or not (campaign or templates):
            return self.root, "target is forbidden"
        allowed = self.root / ("markdown_files" if campaign else "outside game/templates")
        path = (self.root / target).resolve()
        try:
            path.relative_to(allowed.resolve())
        except ValueError:
            return path, "target escapes allowed root"
        return path, None

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_id(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
        atomic_json(path, value)

    @staticmethod
    def _public_change(item: dict[str, Any]) -> dict[str, Any]:
        return {key: item.get(key) for key in ("target_file", "action", "template", "before_hash", "after_hash", "reason")}


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply an approved outside-game Markdown proposal")
    parser.add_argument("proposal", help="Proposal JSON file or '-'")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raw = sys.stdin.read() if args.proposal == "-" else Path(args.proposal).read_text(encoding="utf-8")
    result = AdminEditor(ROOT).apply(json.loads(raw), dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
