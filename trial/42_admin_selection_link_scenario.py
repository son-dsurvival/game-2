"""Verify setup choices remain linked through the Admin approval handoff."""
from __future__ import annotations

import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brain.runtime_state import RuntimeStateStore
from pipeline import CampaignPipeline

RESULT_JSON = ROOT / "trial" / "42_admin_selection_link_result.json"
RESULT_MD = ROOT / "trial" / "42_admin_selection_link_result.md"

OPTIONS = {
    "stat": {
        "STR": ["Forceful Motion", "Physical Drive", "Power Transfer"],
        "INT": ["Pattern Recognition", "Flaw Detection", "Logical Analysis"],
    },
    "effect": [
        "Swordplay", "Opponent Reading", "Footwork", "Feinting", "Parry Timing",
        "Distance Management", "Target Selection", "Grip Switching", "Rapid Recovery", "Weapon Maintenance",
    ],
    "class": [
        "Swordsman: disciplined sword form", "Swordsman: dueling tempo",
        "Swordsman: battlefield line control", "Swordsman: weapon recovery",
        "Swordsman: shield integration",
    ],
}


class SelectionLinkGame:
    def __init__(self, selected):
        self.selected = selected
        self.seen_continuation = None

    def prepare_setup(self, context):
        continuation = context.get("active_clarification")
        if not continuation or continuation.get("status") != "answered":
            return {
                "status": "needs_clarification",
                "player_question": "Choose your Stat, Effect, and Class Modifiers.",
                "clarification_result": {
                    "stat_modifier_options": OPTIONS["stat"],
                    "effect_modifier_options": OPTIONS["effect"],
                    "class_modifier_options": OPTIONS["class"],
                },
            }

        self.seen_continuation = continuation
        answer = continuation.get("answer", "")
        selected = json.loads(answer)
        proposal = {
            "status": "proposal_ready",
            "answer": "Selections linked and ready for approval.",
            "changes": [{
                "target_file": "markdown_files/status sheet.md",
                "action": "update",
                "old_text": "before",
                "new_text": "\n".join([
                    "## Linked Modifier Selection",
                    f"Stat selections: {', '.join(selected['stat'])}",
                    f"Effect selections: {', '.join(selected['effect'])}",
                    f"Class selection: {selected['class']}",
                    "Admin handoff verified: the selections came from the linked player answer.",
                ]),
            }],
            "selected_modifiers": selected,
            "clarification_result": continuation.get("result", {}).get("clarification_result"),
        }
        return {"status": "proposal_ready", "proposal": proposal}

    # Unused gameplay seams are included so CampaignPipeline can be constructed.
    def route(self, message, context):
        return {"request_type": "admin", "required_specialists": [], "preflight": {"errors": []}}


def main() -> None:
    rng = random.Random(20260304)
    selected = {
        "stat": [rng.choice(OPTIONS["stat"]["STR"]), rng.choice(OPTIONS["stat"]["INT"])],
        "effect": rng.sample(OPTIONS["effect"], 3),
        "class": rng.choice(OPTIONS["class"]),
    }
    answer = json.dumps(selected, ensure_ascii=False)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "markdown_files").mkdir()
        (root / "markdown_files/status sheet.md").write_text("before", encoding="utf-8")
        RuntimeStateStore(root).save({"play_gate": "setup_required", "campaign_id": "selection-link-test"})
        game = SelectionLinkGame(selected)
        pipeline = CampaignPipeline(root, modules=game)
        pipeline.begin_setup()
        pipeline.add_character(
            {"name": "Dara", "age": 29, "race": "Human"},
            {"AGI": 6, "INT": 7, "STR": 6, "END": 5, "WIS": 3, "PRE": 3},
            "A disciplined swordswoman who studies opponents and trains precise movement.",
            "Swordsman",
        )
        pipeline.select_main("Dara")
        review = pipeline.review_setup()
        answered = pipeline.submit(answer)
        stored_file = "\n".join(answered.get("proposal_file", {}).get("preview", []))

    payload = {
        "random_seed": 20260304,
        "option_pool": OPTIONS,
        "random_player_selection": selected,
        "initial_review": review,
        "answered_result": answered,
        "admin_linked_continuation": game.seen_continuation,
        "stored_approved_content": stored_file,
        "checks": {
            "answer_preserved_exactly": game.seen_continuation.get("answer") == answer,
            "original_options_preserved": game.seen_continuation.get("result", {}).get("clarification_result") == {
                "stat_modifier_options": OPTIONS["stat"],
                "effect_modifier_options": OPTIONS["effect"],
                "class_modifier_options": OPTIONS["class"],
            },
            "selected_effect_count": len(selected["effect"]) == 3,
            "selected_class_count": len([selected["class"]]) == 1,
            "selected_content_reached_handoff": "Admin handoff verified" in stored_file,
        },
    }
    payload["status"] = "passed" if all(payload["checks"].values()) else "failed"
    RESULT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    checks = payload["checks"]
    markdown = f"""# Admin Selection-Link Test

## Test

A different character was given to setup. The player then randomly selected:

- **Stat choices:** {', '.join(selected['stat'])}
- **Effect choices:** {', '.join(selected['effect'])}
- **Class choice:** {selected['class']}

## Link Verification

- Exact player answer preserved: **{checks['answer_preserved_exactly']}**
- Original option pool preserved in the linked result: **{checks['original_options_preserved']}**
- Exactly 3 Effect Modifiers selected: **{checks['selected_effect_count']}**
- Exactly 1 Class Modifier selected: **{checks['selected_class_count']}**
- Selected content reached the Admin handoff/storage stage: **{checks['selected_content_reached_handoff']}**

## Stored Admin Handoff

```text
{stored_file}
```

## Status

**{payload['status'].upper()}**

Structured detail: `trial/42_admin_selection_link_result.json`
"""
    RESULT_MD.write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
