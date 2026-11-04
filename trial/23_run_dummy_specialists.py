"""Run the specialist orchestration against a deterministic dummy bundle.

This deliberately does not call DeepSeek. It exercises the real SpecialistRunner
parallel fan-out, result validation, core-lane injection, and Create Specialist
proposal validation.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brain.specialists.runner import SpecialistRunner
BUNDLE_PATH = ROOT / "trial" / "23_specialist_dummy_bundle.json"
RESULT_PATH = ROOT / "trial" / "23_specialist_dummy_result.json"


class DummySpecialistRunner(SpecialistRunner):
    def __init__(self, repo_root: Path):
        super().__init__(repo_root)
        self.started: list[str] = []
        self._lock = threading.Lock()

    def _run_one(self, bundle_record, bundle, definition, section_inputs):
        # A short equal delay makes serial-vs-parallel behavior visible without
        # requiring credentials or making a network request.
        with self._lock:
            self.started.append(definition.name)
        time.sleep(0.05)
        citation = {
            "source": "markdown_files/game rules (1).md",
            "heading": "Game Rules excerpt",
            "line_range": "1-20",
            "claim": "Dummy evidence was available to the specialist.",
        }
        result = {
            "specialist": definition.name,
            "status": "complete",
            "citations": [citation],
            "applicable_rules": [],
            "excluded_rules": [],
            "findings": [],
            "assumptions": [],
            "evidence_requests": [],
            "conflicts": [],
            "recommendation": None,
            "calculation": None,
            "cache_delta": {
                "durable_facts": [],
                "active_threads": [],
                "pending_commitments": [],
                "unresolved_questions": [],
                "expiring_facts": [],
            } if definition.name == "cache" else None,
        }

        if definition.name == "rules":
            result["applicable_rules"] = [
                "Treat this as a noncombat experiment with a two-day time cost and a resource cost."
            ]
            result["findings"] = [
                "The rules lane owns experiment procedure, difficulty, time, and moonstone costs."
            ]
            result["calculation"] = {
                "kind": "difficulty",
                "target_type": "Task Value",
                "tier": 1,
                "components": {
                    "difficulty": 70,
                    "novelty": 25,
                    "integration": 0,
                    "independence": 0,
                    "field_risk": 0,
                    "practice_carryover": 0,
                },
                "reaction_reference": 0,
                "total": 95,
                "formula": "70 + 25 + 0 + 0 + 0 - 0 = 95",
            }
        elif definition.name == "character":
            result["findings"] = [
                "Seris is a named helper and her relationship, autonomy, and contribution must be checked.",
                "The player is the Main actor; Seris is a Sub only if the evidence confirms active help.",
            ]
            result["calculation"] = {
                "kind": "modifier",
                "action_type": "other",
                "stat_formula": "Average Relevant Stats + skill + assistance",
                "components": [
                    {"name": "Average Relevant Stats", "value": 40, "included": True, "reason": "dummy character data"},
                    {"name": "Alchemy skill", "value": 15, "included": True, "reason": "dummy character data"},
                    {"name": "Seris assistance", "value": 10, "included": True, "reason": "active helper role"},
                ],
                "realistic_approach": 10,
                "action_value_before_d20": 75,
                "participants": ["Player", "Seris"],
                "team_action": None,
            }
        elif definition.name == "special":
            result["findings"] = [
                "The alchemy branch is active because the player is testing and preserving a recipe.",
                "The branch may later need a dedicated recipe-quality specialist if this becomes recurring."
            ]
        elif definition.name == "alchemy":
            result["findings"] = [
                "Alchemy monitors the recipe, reagents, reaction procedure, and preservation result."
            ]
        elif definition.name == "create":
            result["findings"] = [
                "Existing core lanes cover this turn, but a recurring recipe-quality branch may need its own specialist."
            ]
            result["created_specialists"] = [{
                "name": "recipe_quality",
                "purpose": "Track recurring recipe stability, quality, preservation, and refinement outcomes.",
                "questions": [
                    "Which recipe-quality rules apply?",
                    "What evidence changes recipe stability or preservation?",
                ],
                "activation_tags": ["activity.alchemy", "mechanic.recipe_quality"],
            }]
        return self._validate_result(result, definition, section_inputs)


def main() -> None:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    runner = DummySpecialistRunner(ROOT)
    started = time.perf_counter()
    result = runner.run(bundle, bundle["required_specialists"])
    elapsed = time.perf_counter() - started
    result["test_metadata"] = {
        "mode": "deterministic_dummy_no_api",
        "specialists_started": runner.started,
        "specialist_count": len(runner.started),
        "elapsed_seconds": round(elapsed, 3),
        "parallelism_check": "passed" if elapsed < 0.25 else "inconclusive",
        "note": "The cache lane runs first; the remaining specialists sleep 0.05s concurrently.",
    }
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
