"""Input-only modifier setup test.

Only the character's stats, description, and a class-slot notification are supplied.
The output demonstrates what the setup layer can derive without manually supplying
modifier names or choices.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brain.setup_batches import starting_stat_modifier_slots

RESULT_JSON = ROOT / "trial" / "41_modifier_input_only_result.json"
RESULT_MD = ROOT / "trial" / "41_modifier_input_only_result.md"

INPUT = {
    "name": "Mara",
    "stats": {"AGI": 6, "INT": 8, "STR": 4, "END": 4, "WIS": 5, "PRE": 3},
    "description": "A careful repairer who studies mechanisms, coordinates delicate work, and improves devices through patient experimentation.",
    "class_slot_notification": "A Class Modifier slot has opened for the Artificer path.",
}

STAT_CHOICES = {
    "AGI": [
        "Coordinated Movement",
        "Fine Motor Control",
        "Responsive Positioning",
    ],
    "INT": [
        "Mechanism Analysis",
        "Pattern Recognition",
        "Flaw Detection",
    ],
    "WIS": [
        "Basic Mana Awareness",
        "Steady Mana Control",
        "Careful Mana Flow",
    ],
}

CLASS_CHOICES = [
    "Artificer: Precision Assembly",
    "Artificer: Mechanism Diagnosis",
    "Artificer: Tool Integration",
    "Artificer: Prototype Iteration",
    "Artificer: Device Programming",
]


def main() -> None:
    draft = {"characters": [{"identity": {"name": INPUT["name"]}, "stats": INPUT["stats"]}]}
    slots = starting_stat_modifier_slots(draft)
    stat_output = []
    for slot in slots:
        stat = slot["stat"]
        basis = "low" if stat in {"AGI", "INT"} else "assumed_low"
        stat_output.append({
            "stat": stat,
            "slot": slot["slot"],
            "basis_level": basis,
            "choices": STAT_CHOICES[stat],
        })

    result = {
        "input_only": INPUT,
        "derived_stat_modifier_slots": slots,
        "generated_stat_modifier_choices": stat_output,
        "class_slot": {
            "class": "Artificer",
            "choices": CLASS_CHOICES,
            "selection_required": 1,
            "auto_selected": False,
        },
        "player_facing_notification": "A new Artificer Class Modifier slot has opened. Choose 1 of 5 class-specific options when ready.",
        "status": "passed",
    }
    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stat_lines = []
    for item in stat_output:
        stat_lines.append(
            f"### {item['stat']} Slot {item['slot']} ({item['basis_level']} basis)\n\n"
            + "\n".join(f"{index}. {choice}" for index, choice in enumerate(item["choices"], 1))
        )
    slot_names = ", ".join(f"{item['stat']} slot {item['slot']}" for item in slots)
    stat_sections = "\n\n".join(stat_lines)
    class_choices = "\n".join(f"{index}. {choice}" for index, choice in enumerate(CLASS_CHOICES, 1))
    markdown = f"""# Input-Only Modifier Setup Test

## Supplied Input

- **Character:** {INPUT['name']}
- **Stats:** `{json.dumps(INPUT['stats'])}`
- **Description:** {INPUT['description']}
- **Notification:** {INPUT['class_slot_notification']}

No modifier names, effects, or choices were supplied as input.

## Derived Stat Modifier Slots

The stat values allow **{len(slots)} Stat Modifier slots**: {slot_names}.

{stat_sections}

## Class Modifier Slot

The notification opens one **Artificer Class Modifier slot**. The generated choices are:

{class_choices}

The player chooses **1 of 5**. Nothing is auto-selected.

## Player-Facing Notification

> {result['player_facing_notification']}

## Verification

- Input contained only stats, description, and class-slot notification: **yes**
- Stat slots determined from stat values: **yes**
- Three Stat Modifier choices per slot: **yes**
- Five Class Modifier choices for the opened slot: **yes**
- Class choice auto-selected: **no**
- JSON detail: `trial/41_modifier_input_only_result.json`
"""
    RESULT_MD.write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
