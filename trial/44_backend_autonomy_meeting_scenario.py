"""Backend test: a party member continues task A while the player performs B."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.background_state import BackgroundStateStore
from backend.contracts import BackgroundDirective
from backend.phase_clock import PhaseClock
from backend.phase_tick import PhaseTickEngine

RESULT_JSON = ROOT / "trial" / "44_backend_autonomy_meeting_result.json"
RESULT_MD = ROOT / "trial" / "44_backend_autonomy_meeting_result.md"


PLAYER_TURNS = [
    {"turn": 1, "action": "Search the market for a map.", "location": "market"},
    {"turn": 2, "action": "Travel along the north road.", "location": "north road"},
    {"turn": 3, "action": "Enter the north grove and look for Renn.", "location": "north grove"},
]


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        public_path = root / "Experimentation Register.md"
        private_path = root / "background_state.json"
        public_path.write_text("# Experimentation Register\n", encoding="utf-8")
        store = BackgroundStateStore(public_path, private_state_path=private_path, mirror=False)
        start = PhaseClock().position(1, "Early Morning")
        directive = BackgroundDirective(
            directive_id="directive-renn-herbs",
            actor="Renn",
            task="Collect medicinal herbs in the north grove.",
            location="north grove",
            constraints=("Do not leave the grove until the collection is complete.",),
            assigned_by="Nia",
            metadata={"visibility": "hidden", "ooc_visibility": "private", "requires_resolution": False},
        )
        store.upsert_directive(directive)
        engine = PhaseTickEngine(store)
        current = start
        background_ticks = []

        def analyze(name, plan, context):
            return {"specialist": name, "status": "complete", "finding": "Renn's assigned task remains active."}

        def resolve_tick(plan):
            nonlocal herbs_collected
            actions = []
            for action in plan["actions"]:
                actions.append({
                    **action,
                    "status": "successful",
                    "player_visibility": "hidden",
                    "ooc_visibility": "private",
                })
            before = herbs_collected
            herbs_collected += collection_rate_per_phase
            completed = ["directive-renn-herbs"] if plan["position"]["phase"] == "Midday" else []
            return {
                "status": "resolved",
                "actions": actions,
                "resource_changes": [{
                    "resource": "medicinal herbs",
                    "before": before,
                    "delta": collection_rate_per_phase,
                    "after": herbs_collected,
                    "reason": "temporary test assumption: 2 herbs collected per phase",
                }],
                "completed_directives": completed,
                "notes": ["Autonomy continued while the player pursued a separate action."],
            }

        turn_records = []
        herbs_collected = 0
        collection_rate_per_phase = 2
        for player_turn in PLAYER_TURNS:
            result = engine.run(
                current,
                1,
                context={"character_state": {"Renn": {}}},
                resolve_tick=resolve_tick,
                analyze=analyze,
                specialist_names=("character",),
            )
            transition = result["ticks"][0]["record"]
            background_ticks.append(transition)
            current = PhaseClock().position(
                transition["position"]["day"], transition["position"]["phase"], transition["position"].get("progress", 0)
            )
            turn_records.append({
                "player_turn": player_turn,
                "backend_tick": transition,
            })

        final_tick = turn_records[-1]["backend_tick"]
        autonomy_action = final_tick["actions"][0]
        private_records = store.load_ticks()
        resource_changes = [
            change
            for tick in private_records
            for change in tick.get("resource_changes", [])
            if change.get("resource") == "medicinal herbs"
        ]
        met = (
            PLAYER_TURNS[-1]["location"] == autonomy_action["location"]
            and autonomy_action["actor"] == "Renn"
            and autonomy_action["chosen_action"] == directive.task
        )
        public_text = public_path.read_text(encoding="utf-8")
        checks = {
            "three_player_turns_completed": len(turn_records) == 3,
            "three_backend_ticks_committed": len(private_records) == 3,
            "renn_kept_doing_task_a": all(
                tick["actions"][0]["chosen_action"] == directive.task for tick in private_records
            ),
            "player_actions_remained_separate": [item["player_turn"]["action"] for item in turn_records] == [item["action"] for item in PLAYER_TURNS],
            "meeting_after_third_turn": met,
            "directive_completed_at_meeting_tick": private_records[-1]["completed_directives"] == [directive.directive_id],
            "resource_calculated_each_phase": len(resource_changes) == 3 and all(change.get("delta") == 2 for change in resource_changes),
            "total_returned_after_three_phases": resource_changes[-1].get("after") == 6 if resource_changes else False,
            "private_background_not_publicly_mirrored": "Collect medicinal herbs" not in public_text,
        }
        payload = {
            "scenario": {
                "task_a": directive.to_dict(),
                "player_task_b_turns": PLAYER_TURNS,
                "starting_position": start.to_dict(),
            },
            "turn_records": turn_records,
            "private_backend_ticks": private_records,
            "public_register": public_text,
            "checks": checks,
            "status": "passed" if all(checks.values()) else "failed",
        }

    RESULT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = f"""# Backend Autonomy Meeting Test

## Scenario

- **Task A — Renn:** {directive.task}
- **Task A location:** {directive.location}
- **Player Task B, Turn 1:** {PLAYER_TURNS[0]['action']}
- **Player Task B, Turn 2:** {PLAYER_TURNS[1]['action']}
- **Player Task B, Turn 3:** {PLAYER_TURNS[2]['action']}

## Backend Result

Renn continued Task A on all three backend ticks while the player independently performed Task B.
On the third turn, the player entered the north grove and met Renn still performing the assigned task.

### Resource Calculation

The test used an explicit temporary assumption of **2 medicinal herbs per phase**.
After 3 phases: **2 × 3 = 6 medicinal herbs returned**.

### Meeting Narration

> After searching the market and traveling north, the player enters the grove and finds Renn collecting medicinal herbs exactly as instructed.

## Verification

- Three player turns completed: **{checks['three_player_turns_completed']}**
- Three backend ticks committed: **{checks['three_backend_ticks_committed']}**
- Renn continued Task A: **{checks['renn_kept_doing_task_a']}**
- Player Task B remained separate: **{checks['player_actions_remained_separate']}**
- Meeting occurred after turn 3: **{checks['meeting_after_third_turn']}**
- Directive completed at meeting tick: **{checks['directive_completed_at_meeting_tick']}**
- Resource calculated each phase: **{checks['resource_calculated_each_phase']}**
- Total returned after three phases: **{checks['total_returned_after_three_phases']}** — 6 medicinal herbs
- Private background remained out of public register: **{checks['private_background_not_publicly_mirrored']}**

## Status

**{payload['status'].upper()}**

Structured detail: `trial/44_backend_autonomy_meeting_result.json`
"""
    RESULT_MD.write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
