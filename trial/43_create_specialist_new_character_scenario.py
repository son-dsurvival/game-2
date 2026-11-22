"""Verify a new character can produce a safe Create Specialist proposal."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brain.runtime_state import RuntimeStateStore
from brain.specialists.character_group import character_specialist_group
from pipeline import CampaignPipeline

RESULT_JSON = ROOT / "trial" / "43_create_specialist_new_character_result.json"
RESULT_MD = ROOT / "trial" / "43_create_specialist_new_character_result.md"

CHARACTER = {
    "identity": {"name": "Nia", "age": 27, "race": "Human"},
    "stats": {"AGI": 6, "INT": 6, "STR": 5, "END": 5, "WIS": 4, "PRE": 4},
    "description": "A patient field naturalist who tracks, calms, and trains injured wild beasts.",
    "class": "Ranger",
}

SPECIALIST_PROPOSALS = character_specialist_group(CHARACTER, assumption_authorized=True)


class NewCharacterCreateGame:
    def route(self, message, context):
        return {
            "request_type": "in_game",
            "required_specialists": ["cache", "rules", "character", "create"],
            "preflight": {"errors": []},
        }

    def evidence(self, route, context, note=None):
        return {"turn_id": route["turn_id"], "current_state": context}

    def specialists(self, bundle, context, extra=()):
        return {
            "turn_id": bundle["turn_id"],
            "specialist_results": [
                {"specialist": "character", "status": "complete", "finding": "Nia requires a character-scoped context grounded in her description."},
                {"specialist": "create", "status": "complete", "finding": "Create prepared the unique character_nia specialist context."},
            ],
            "coverage_check": {"ready_for_lead_resolver": True},
            "specialist_updates": {"created_specialists": SPECIALIST_PROPOSALS},
        }

    def resolve(self, analysis, context, dice=None):
        return {
            "status": "resolved",
            "resolution_record": {
                "status": "resolved",
                "outcome": "Nia identifies a safe training opportunity and prepares the beast domain for future tracking.",
                "time_changes": [{"phases_elapsed": 0}],
            },
        }

    def narrate(self, resolution, context):
        return {"narration": "Nia's description has been converted into a character-scoped specialist context covering her voice, motives, modifiers, relationships, participation, consent, and autonomy."}

    def record(self, resolution, context):
        return {"status": "recorded", "cache_delta": {}}

    def background(self, transitions, context):
        return {"status": "no_tick_required"}


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        RuntimeStateStore(root).save({
            "play_gate": "open",
            "campaign_id": "new-character-specialist-test",
            "setup_status": "active",
            "main_character": "Nia",
            "party": [CHARACTER],
        })
        pipeline = CampaignPipeline(root, modules=NewCharacterCreateGame())
        result = pipeline.submit("Nia joins the party with a recurring beast-handling practice.")
        proposals = pipeline.specialist_proposals()
        state = RuntimeStateStore(root).load()

    stored = [item for item in proposals if str(item.get("name", "")).startswith("character_nia_")]
    checks = {
        "new_character_present": any(item.get("identity", {}).get("name") == "Nia" for item in state.get("party", [])),
        "five_character_specialists_stored": len(stored) == 5,
        "proposal_is_not_auto_installed": bool(stored) and all(item.get("status") == "proposed" for item in stored),
        "proposals_have_safe_scope": bool(stored) and all(all(key in item for key in ("name", "purpose", "questions", "activation_tags", "sections")) for item in stored),
        "assumptions_are_provisional": bool(stored) and all(item.get("initialization_assumption", {}).get("player_authorized") is True and item.get("initialization_assumption", {}).get("persistence") == "temporary_memory" for item in stored),
    }
    payload = {
        "character": CHARACTER,
        "player_assumption_authorization": "You decide",
        "trigger": "New named character Nia arrived with a field-naturalist description.",
        "pipeline_result": result,
        "stored_specialist_proposals": proposals,
        "checks": checks,
        "status": "passed" if all(checks.values()) else "failed",
    }
    RESULT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    markdown = f"""# Create Specialist — New Character Test

## New Character

- **Name:** Nia
- **Class:** Ranger
- **Stats:** `{json.dumps(CHARACTER['stats'])}`
- **Description:** {CHARACTER['description']}

## Player Assumption Authorization

> You decide

## Trigger

A new named character arrived. The description was converted into a unique character-scoped specialist context rather than a global branch specialist.

## Proposed Specialist

- **Specialist count:** {len(SPECIALIST_PROPOSALS)}
- **Names:** {', '.join(item['name'] for item in SPECIALIST_PROPOSALS)}
- **Sections:** {', '.join(section for item in SPECIALIST_PROPOSALS for section in item['sections'])}
- **Status:** `proposed`

### Questions

{chr(10).join(f'- {item["name"]}: {question}' for item in SPECIALIST_PROPOSALS for question in item['questions'])}

## Verification

- New character present: **{checks['new_character_present']}**
- Five character specialists stored: **{checks['five_character_specialists_stored']}**
- Proposals were not auto-installed: **{checks['proposal_is_not_auto_installed']}**
- Proposals have safe bounded scopes: **{checks['proposals_have_safe_scope']}**
- Assumptions are player-authorized and temporary: **{checks['assumptions_are_provisional']}**

## Narration Result

> {result.get('message', '')}

## Status

**{payload['status'].upper()}**

Structured detail: `trial/43_create_specialist_new_character_result.json`
"""
    RESULT_MD.write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
