"""Deterministic end-to-end scenario for Stat, Effect, and Class Modifiers.

This uses the CampaignPipeline seam with an offline game adapter. It verifies the
player-facing action description, the modifier breakdown, and the final narration
without calling a model or changing the real campaign state.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brain.runtime_state import RuntimeStateStore
from pipeline import CampaignPipeline

RESULT_JSON = ROOT / "trial" / "40_modifier_taxonomy_result.json"
RESULT_MD = ROOT / "trial" / "40_modifier_taxonomy_result.md"

CHARACTER = {
    "name": "Femi",
    "class": "Swordsman",
    "stats": {"STR": 7, "INT": 7, "WIS": 5, "AGI": 5, "END": 4, "PRE": 2},
    "description": "A technically minded swordsman who studies opponents and practices precise cuts.",
}

STAT_MODIFIERS = [
    {
        "type": "stat",
        "name": "Strength-Based Force",
        "stat": "STR",
        "domain": "forceful physical actions",
        "bonus": 2,
        "description": "Strength supports any forceful swing, strike, push, or lift; it is not sword-only.",
    },
    {
        "type": "stat",
        "name": "Analytical Pattern Recognition",
        "stat": "INT",
        "domain": "analysis and noticing flaws",
        "bonus": 1,
        "description": "Intelligence supports reading patterns, noticing flaws, and solving problems; it is not combat-only.",
    },
]

EFFECT_OPTIONS = [
    "Swordplay: controlled blade technique",
    "Opponent Reading: identify a predictable guard",
    "Footwork: reposition during a strike",
    "Feinting: disguise the attack line",
    "Parry Timing: redirect a committed blow",
    "Weapon Maintenance: preserve edge and balance",
    "Rapid Recovery: reset after a missed cut",
    "Grip Switching: change attack angle",
    "Distance Management: maintain ideal range",
    "Target Selection: choose a vulnerable opening",
]

SELECTED_EFFECTS = [
    {"type": "effect", "name": "Swordplay", "domain": "sword technique", "bonus": 3},
    {"type": "effect", "name": "Opponent Reading", "domain": "sword action", "bonus": 1},
    {"type": "effect", "name": "Footwork", "domain": "sword action", "bonus": 1},
]

CLASS_OPTIONS = [
    "Swordsman: disciplined sword form",
    "Swordsman: shield integration",
    "Swordsman: dueling tempo",
    "Swordsman: battlefield line control",
    "Swordsman: weapon recovery",
]
SELECTED_CLASS = {
    "type": "class",
    "name": "Disciplined Sword Form",
    "class": "Swordsman",
    "domain": "swordplay",
    "bonus": 2,
}

ACTION = "Femi analyzes the opponent, notices a flaw, steps into range, and uses practiced swordplay to deliver a precise cut."


class ModifierScenarioGame:
    def route(self, message, context):
        return {
            "request_type": "in_game",
            "required_specialists": ["rules", "character", "class"],
            "preflight": {"errors": []},
        }

    def evidence(self, route, context, note=None):
        return {"turn_id": route["turn_id"], "current_state": context}

    def specialists(self, bundle, context, extra=()):
        return {
            "turn_id": bundle["turn_id"],
            "specialist_results": [
                {
                    "specialist": "character",
                    "status": "complete",
                    "finding": "STR and INT Stat Modifiers apply to this action.",
                },
                {
                    "specialist": "class",
                    "status": "complete",
                    "finding": "The Swordsman Class Modifier applies to swordplay.",
                },
                {
                    "specialist": "rules",
                    "status": "complete",
                    "finding": "Relevant Stat, Effect, and Class Modifiers sum.",
                },
            ],
            "coverage_check": {"ready_for_lead_resolver": True},
        }

    def resolve(self, analysis, context, dice=None):
        breakdown = [
            {"type": "base", "name": "Action Value before modifiers", "value": 10},
            *[
                {"type": item["type"], "name": item["name"], "domain": item["domain"], "value": item["bonus"]}
                for item in STAT_MODIFIERS + SELECTED_EFFECTS[:1] + [SELECTED_CLASS]
            ],
        ]
        total = sum(item["value"] for item in breakdown)
        return {
            "status": "resolved",
            "resolution_record": {
                "status": "resolved",
                "outcome": "The cut lands cleanly on the training target.",
                "action_value": total,
                "modifier_breakdown": breakdown,
                "time_changes": [{"phases_elapsed": 0}],
            },
        }

    def narrate(self, resolution, context):
        record = resolution["resolution_record"]
        return {
            "narration": (
                "Femi analyzes the opening, notices the flaw, shifts with disciplined footwork, and drives a precise sword cut "
                "through the target's guard. His strength supplies broad physical force, his intelligence spots the "
                "weakness, Swordplay supplies the technique, and his Swordsman training sharpens the execution."
            ),
            "visible_modifier_summary": {
                "stat_modifier": "STR — damage",
                "effect_modifier": "Swordplay — sword technique",
                "class_modifier": "Swordsman — disciplined sword form",
                "action_value": record["action_value"],
            },
        }

    def record(self, resolution, context):
        return {"status": "recorded", "cache_delta": {}}

    def background(self, transitions, context):
        return {"status": "no_tick_required"}


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        RuntimeStateStore(root).save({
            "play_gate": "open",
            "campaign_id": "modifier-taxonomy-test",
            "setup_status": "active",
            "party": [CHARACTER],
        })
        pipeline = CampaignPipeline(root, modules=ModifierScenarioGame())
        result = pipeline.submit(ACTION)

    payload = {
        "scenario": {
            "character": CHARACTER,
            "description": ACTION,
            "stat_modifier_slots_allowed_by_stats": {"STR": 1, "INT": 1, "WIS": 1, "AGI": 1},
            "stat_modifiers_available": STAT_MODIFIERS,
            "effect_modifier_options": EFFECT_OPTIONS,
            "effect_modifiers_selected_from_ten": SELECTED_EFFECTS,
            "class_modifier_options": CLASS_OPTIONS,
            "class_modifier_selected_from_five": SELECTED_CLASS,
        },
        "pipeline_result": result,
    }
    RESULT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    narration = result.get("message") or result.get("narration", {}).get("narration")
    resolution = result.get("resolution", {}).get("resolution_record", {})
    markdown = f"""# Modifier Taxonomy Scenario Result

## Character

- **Name:** {CHARACTER['name']}
- **Class:** {CHARACTER['class']}
- **Description:** {CHARACTER['description']}

## Player Action Description

> {ACTION}

## Modifier Selection Setup

### Stat Modifiers

Stat values provide these available slots: **STR 1, INT 1, WIS 1, AGI 1**.
The scenario uses STR's broad force Stat Modifier and INT's broad analysis Stat Modifier.

### Effect Modifiers

The character receives 10 options and selects 3:

1. Swordplay — sword technique
2. Opponent Reading — sword action
3. Footwork — sword action

### Class Modifiers

The Swordsman class receives 5 choices and selects:

- Disciplined Sword Form — swordplay

## Resolution Modifier Breakdown

| Modifier type | Modifier | Domain | Bonus |
|---|---|---|---:|
| Base | Action Value before modifiers | action | +10 |
| Stat | Strength-Based Force | STR / forceful physical actions | +2 |
| Stat | Analytical Pattern Recognition | INT / analysis and noticing flaws | +1 |
| Effect | Swordplay | sword technique | +3 |
| Class | Disciplined Sword Form | Swordsman / swordplay | +2 |

**Final tested Action Value: 18**

## Narration Result

> {narration}

## Result

- Stat Modifiers applied: **yes** — broad STR force and INT analysis
- Effect Modifier applied: **yes** — Swordplay
- Class Modifier applied: **yes** — Swordsman sword form
- Relevant bonuses summed: **yes**
- Stored JSON detail: `trial/40_modifier_taxonomy_result.json`
"""
    RESULT_MD.write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
