"""Verify that resolved branch unlocks affect routing without player claims alone."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brain.branch_registry import BranchRegistry
from brain.recorder import SessionRecorder
from brain.turn_router import TurnRouter

TEMP_PATH = ROOT / "trial" / "27_branch_unlock_temp_memory.md"
RESULT_PATH = ROOT / "trial" / "27_branch_unlock_result.json"


class DummyPlannerRecorder(SessionRecorder):
    def _plan_with_deepseek(self, lead_output):
        return {"turn_id": lead_output["turn_id"], "summary": "Alchemy branch established.", "segments": []}


def main() -> None:
    TEMP_PATH.write_text("## Pending Session Canon\n", encoding="utf-8")
    router = TurnRouter(ROOT, require_git=False)
    before = router.route("I brew an alchemy potion", campaign_mode=True, classifier="heuristic")
    lead_result = {
        "turn_id": "trial-branch-unlock-001",
        "status": "resolved",
        "resolution_record": {
            "turn_id": "trial-branch-unlock-001",
            "status": "resolved",
            "time_changes": [{"day": 2, "phase": "Evening"}],
            "resource_changes": [],
            "modifier_changes": [],
            "branch_candidates": [{
                "branch": "alchemy",
                "status": "candidate",
                "recurring": True,
                "established_evidence": True,
                "description": "Alchemy practice is established.",
            }],
            "branch_changes": [{
                "branch": "alchemy",
                "status": "unlocked",
                "specialist": "alchemy",
                "template": "alchemy.md",
                "activation_tags": ["activity.alchemy"],
                "reason": "The resolved turn established a functioning alchemy practice.",
            }],
        },
    }
    recorder = DummyPlannerRecorder(ROOT, temp_memory_path=TEMP_PATH)
    recorded = recorder.record(lead_result)
    registry = BranchRegistry(ROOT, temp_memory_path=TEMP_PATH)
    router.branch_registry = registry
    after = router.route("I brew an alchemy potion", campaign_mode=True, classifier="heuristic")
    result = {
        "before_unlock": {
            "required_specialists": before.required_specialists,
            "alchemy_routed": "alchemy" in before.required_specialists,
        },
        "recorded": recorded,
        "registry": {
            "alchemy_unlocked": registry.is_unlocked("alchemy"),
            "entry": registry.entry("alchemy"),
        },
        "after_unlock": {
            "required_specialists": after.required_specialists,
            "alchemy_routed": "alchemy" in after.required_specialists,
        },
        "status": "passed" if (
            "alchemy" not in before.required_specialists
            and registry.is_unlocked("alchemy")
            and "alchemy" in after.required_specialists
        ) else "failed",
        "temp_memory": TEMP_PATH.read_text(encoding="utf-8"),
    }
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    TEMP_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
