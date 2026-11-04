"""Exercise recorder state updates from structured Lead Resolver values."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brain.recorder import SessionRecorder

LEAD_PATH = ROOT / "trial" / "24_recorder_dummy_lead_result.json"
TEMP_PATH = ROOT / "trial" / "24_recorder_temp_memory.md"
RESULT_PATH = ROOT / "trial" / "24_recorder_result.json"


class DummyPlannerRecorder(SessionRecorder):
    """Keep the test offline while using the real record/write path."""

    def _plan_with_deepseek(self, lead_output):
        return {
            "turn_id": lead_output["turn_id"],
            "summary": "Dummy resolved turn: spell cast and purchase completed.",
            "segments": [],
        }


def main() -> None:
    lead = json.loads(LEAD_PATH.read_text(encoding="utf-8"))
    TEMP_PATH.write_text("## Pending Session Canon\n", encoding="utf-8")
    recorder = DummyPlannerRecorder(
        ROOT,
        temp_memory_path=TEMP_PATH,
        section_index_path=ROOT / "trial" / "24_missing_section_index.json",
    )
    result = recorder.record(lead)
    result["temp_memory"] = TEMP_PATH.read_text(encoding="utf-8")
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
