"""Full player -> pipeline -> backend -> meeting cycle test."""
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
from brain.runtime_state import RuntimeStateStore
from pipeline import CampaignPipeline

RESULT_JSON = ROOT / "trial" / "45_full_player_backend_cycle_result.json"
RESULT_MD = ROOT / "trial" / "45_full_player_backend_cycle_result.md"

PROMPTS = [
    "Tell Renn to collect medicinal herbs in the north grove. I search the market for a map.",
    "Travel along the north road.",
    "Enter the north grove and meet Renn.",
]


class FullCycleGame:
    """Offline adapter with the same backend seam used by GameModules.background."""

    def __init__(self, root: Path):
        self.root = root
        self.background_calls = 0
        self.backend_lead_resolutions = []
        self.assignment_created = False
        self.herbs_total = 0
        self.store = BackgroundStateStore(
            root / "background_visible.md",
            private_state_path=root / "background_state.json",
            mirror=False,
        )

    def route(self, message, context):
        return {"request_type": "in_game", "required_specialists": ["rules", "character"], "preflight": {"errors": []}}

    def evidence(self, route, context, note=None):
        return {"turn_id": route["turn_id"], "current_state": context}

    def specialists(self, bundle, context, extra=()):
        return {
            "turn_id": bundle["turn_id"],
            "specialist_results": [
                {"specialist": "rules", "status": "complete", "finding": "Backend task and gathering assumption are bounded."},
                {"specialist": "character", "status": "complete", "finding": "Renn can continue the assigned herb task."},
            ],
            "coverage_check": {"ready_for_lead_resolver": True},
        }

    def resolve(self, analysis, context, dice=None):
        message = str(context.get("message", ""))
        if not self.assignment_created and "Tell Renn" in message:
            self.assignment_created = True
        return {
            "status": "resolved",
            "resolution_record": {
                "status": "resolved",
                "outcome": "The player continues their declared action.",
                "time_changes": [{"phases_elapsed": 1}],
            },
        }

    def narrate(self, resolution, context):
        return {"narration": "The player continues toward the north grove."}

    def record(self, resolution, context):
        return {"status": "recorded", "cache_delta": {}}

    def background(self, transitions, context):
        self.background_calls += len(transitions)
        if self.assignment_created:
            existing = {item.directive_id for item in self.store.load_directives()}
            if "directive-renn-herbs" not in existing:
                self.store.upsert_directive(BackgroundDirective(
                    directive_id="directive-renn-herbs",
                    actor="Renn",
                    task="Collect medicinal herbs in the north grove.",
                    location="north grove",
                    assigned_by="player",
                    metadata={"visibility": "hidden", "ooc_visibility": "private", "requires_resolution": True},
                ))

        clock = PhaseClock()
        result = {"status": "complete", "ticks": []}
        for transition in transitions:
            before = clock.position(transition["previous"]["day"], transition["previous"]["phase"])

            def resolve_backend_tick(plan):
                before_count = self.herbs_total
                self.herbs_total += 2  # explicit test assumption: 2 herbs per backend phase
                resolution = {
                    "status": "resolved",
                    "actions": [{
                        **plan["actions"][0],
                        "status": "successful",
                        "player_visibility": "hidden",
                        "ooc_visibility": "private",
                    }],
                    "resource_changes": [{
                        "resource": "medicinal herbs",
                        "before": before_count,
                        "delta": 2,
                        "after": self.herbs_total,
                        "reason": "temporary test assumption: 2 herbs per phase",
                    }],
                    "completed_directives": ["directive-renn-herbs"] if plan["position"]["phase"] == "Midday" else [],
                    "notes": ["Lead Resolver test adapter resolved the autonomous action."],
                }
                self.backend_lead_resolutions.append({"plan": plan, "resolution": resolution})
                return resolution

            tick_result = PhaseTickEngine(self.store).run(
                before,
                1,
                context={"character_state": {"Renn": {}}},
                resolve_tick=resolve_backend_tick,
                specialist_names=("character",),
            )
            result["ticks"].extend(tick_result.get("ticks", []))
            if tick_result.get("status") != "complete":
                result["status"] = tick_result.get("status")
                return result

        player_message = str(context.get("message", ""))
        if "Enter the north grove" in player_message and result["ticks"]:
            action = result["ticks"][-1]["record"]["actions"][0]
            result["status"] = "interrupted"
            result["interrupt"] = {
                "visibility": "visible",
                "message": f"Renn is here, still collecting medicinal herbs. The backend records {self.herbs_total} herbs gathered.",
            }
        return result


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "background_visible.md").write_text("# Private test mirror\n", encoding="utf-8")
        RuntimeStateStore(root).save({
            "play_gate": "open",
            "campaign_id": "full-backend-cycle-test",
            "setup_status": "active",
            "main_character": "Player",
            "party": [
                {"identity": {"name": "Player"}},
                {"identity": {"name": "Renn"}},
            ],
        })
        game = FullCycleGame(root)
        pipeline = CampaignPipeline(root, modules=game)
        turn_results = [pipeline.submit(prompt) for prompt in PROMPTS]
        ticks = game.store.load_ticks()
        final_state = RuntimeStateStore(root).load()
        result = {
            "player_prompts": PROMPTS,
            "turn_results": turn_results,
            "backend_ticks": ticks,
            "backend_lead_resolutions": game.backend_lead_resolutions,
            "background_calls": game.background_calls,
            "final_message": final_state.get("message", ""),
            "final_herb_total": game.herbs_total,
            "checks": {
                "player_cycle_entered_backend": game.background_calls == 3 and len(ticks) == 3,
                "backend_resolved_each_tick": len(game.backend_lead_resolutions) == 3 and all(item["resolution"]["status"] == "resolved" for item in game.backend_lead_resolutions),
                "backend_calculated_resources": game.herbs_total == 6 and ticks[-1]["resource_changes"][-1]["after"] == 6,
                "player_met_character_after_third_turn": "Renn is here" in final_state.get("message", ""),
                "meeting_revealed_result": "6 herbs gathered" in final_state.get("message", ""),
            },
        }
        result["status"] = "passed" if all(result["checks"].values()) else "failed"

    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checks = result["checks"]
    markdown = f"""# Full Player -> Backend -> Meeting Cycle

## Player Prompts

1. `{PROMPTS[0]}`
2. `{PROMPTS[1]}`
3. `{PROMPTS[2]}`

## 1. Did the game correctly turn to the backend?

**{checks['player_cycle_entered_backend']}** — three player turns created three private backend phase ticks.

## 2. Backend resolution

The backend Lead Resolver test adapter resolved Renn's autonomous action on every tick.
The test assumption was **2 medicinal herbs per phase**:

```text
2 herbs x 3 phases = 6 herbs
```

- Backend resolutions: **{len(game.backend_lead_resolutions)}**
- Final herb total: **{result['final_herb_total']}**
- Resources calculated: **{checks['backend_calculated_resources']}**

## 3. Result after the player meets Renn

> {result['final_message']}

- Player met Renn after turn three: **{checks['player_met_character_after_third_turn']}**
- Calculated result was revealed: **{checks['meeting_revealed_result']}**

## Status

**{result['status'].upper()}**

Structured detail: `trial/45_full_player_backend_cycle_result.json`
"""
    RESULT_MD.write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
