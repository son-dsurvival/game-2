"""Exercise the outside-game request, evidence, agent, approval, and editor flow."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTSIDE = ROOT / "outside game"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(OUTSIDE))

from admin_agent import AdminAgent
from admin_editor import AdminEditor
from approval import approve_proposal, bind_source_versions
from brain.evidence_bundle import EvidenceBundleBuilder
from brain.turn_router import TurnRouter

RESULT_PATH = ROOT / "trial" / "26_admin_dummy_result.json"
DUMMY_FILE = ROOT / "markdown_files" / "__admin_dummy__.md"


def main() -> None:
    run_id = uuid.uuid4().hex[:8]
    router = TurnRouter(ROOT, require_git=False)
    routed = router.route(
        "{ Why is Seris's relationship status wrong? Please investigate the records. }",
        campaign_mode=False,
        turn_active=True,
        classifier="heuristic",
    )
    bundle = EvidenceBundleBuilder(ROOT).build(routed.to_dict(), selector="heuristic")
    bundle_record = routed.to_dict()
    bundle_record["evidence_bundle"] = bundle.to_dict()
    dummy_answer = AdminAgent(ROOT).respond(bundle_record, mode="dummy")

    DUMMY_FILE.write_text("# Admin Dummy\n\nValue: 1\n- temporary\n", encoding="utf-8")
    editor = AdminEditor(ROOT)
    update = approve_proposal(bind_source_versions({
        "request_id": f"admin-editor-update-{run_id}",
        "status": "proposal_ready",
        "proposed_by": "admin_agent",
        "changes": [{
            "target_file": "markdown_files/__admin_dummy__.md",
            "action": "update",
            "old_text": "Value: 1",
            "new_text": "Value: 2",
            "reason": "Dummy approved update",
        }],
    }, repo_root=ROOT))
    update_result = editor.apply(update)
    delete = approve_proposal(bind_source_versions({
        "request_id": f"admin-editor-delete-{run_id}",
        "status": "proposal_ready",
        "proposed_by": "admin_agent",
        "changes": [{
            "target_file": "markdown_files/__admin_dummy__.md",
            "action": "delete",
            "old_text": "- temporary\n",
            "new_text": "",
            "reason": "Dummy approved deletion",
        }],
    }, repo_root=ROOT))
    delete_result = editor.apply(delete)
    create = approve_proposal(bind_source_versions({
        "request_id": f"admin-editor-create-{run_id}",
        "status": "proposal_ready",
        "proposed_by": "admin_agent",
        "changes": [{
            "target_file": "markdown_files/__admin_created__.md",
            "action": "create",
            "template": "ledger_resources",
            "values": {"current MP": 100, "money": 50},
            "old_text": "",
            "new_text": "",
            "reason": "Dummy approved templated creation",
        }],
    }, repo_root=ROOT))
    create_result = editor.apply(create)
    created_file = ROOT / "markdown_files" / "__admin_created__.md"
    final_text = DUMMY_FILE.read_text(encoding="utf-8")
    created_text = created_file.read_text(encoding="utf-8")
    DUMMY_FILE.unlink(missing_ok=True)
    created_file.unlink(missing_ok=True)

    result = {
        "routing": {
            "request_type": routed.request_type,
            "admin_request": routed.admin_request,
            "preflight_errors": routed.preflight["errors"],
            "status": "passed" if routed.request_type == "admin" and not routed.preflight["errors"] else "failed",
        },
        "evidence_bundle": {
            "selection_source": bundle.selection_source,
            "selected_section_count": len(bundle.selected_sections),
            "admin_source_count": len(bundle.admin_sources),
            "status": "passed" if bundle.selection_source.startswith("admin_") else "failed",
        },
        "admin_agent": {
            "response": dummy_answer,
            "status": "passed" if dummy_answer["status"] == "answered" and not dummy_answer["changes"] else "failed",
        },
        "admin_editor": {
            "update": update_result,
            "delete": delete_result,
            "create": create_result,
            "final_updated_file": final_text,
            "created_file": created_text,
            "status": "passed" if all(item["status"] == "applied" for item in (update_result, delete_result, create_result)) and final_text == "# Admin Dummy\n\nValue: 2\n" else "failed",
        },
    }
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
