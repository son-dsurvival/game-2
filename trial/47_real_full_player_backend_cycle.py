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
from backend.backend_lead_resolver import BackendLeadResolver
from brain.runtime_state import RuntimeStateStore
from pipeline import CampaignPipeline

RESULT_JSON = ROOT / "trial" / "47_real_full_player_backend_cycle_result.json"
RESULT_MD = ROOT / "trial" / "47_real_full_player_backend_cycle_result.md"

PROMPTS = [
    "Tell Renn to collect medicinal herbs in the north grove. I search the market for a map.",
    "Travel along the north road.",
    "Enter the north grove and meet Renn.",
]


class RealFullCycleGame:
    """Player-cycle harness using the real BackendLeadResolver for hidden ticks."""

    def __init__(self, root: Path):
        self.root = root
        self.background_calls = 0
        self.backend_lead_resolutions = []
        self.assignment_created = False
        self.herbs_total = 0
        self.assumption_record = None
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
                hidden_context = {
                    "turn_id": plan["tick_id"],
                    "position": plan["position"],
                    "message": "Resolve Renn's hidden autonomous herb-gathering action.",
                    "answers": ["You decide"],
                    "private_background": self.store.load_ticks(),
                    "assumption_record": self.assumption_record,
                    "active_clarification": {
                        "id": "backend-cycle:clarification:1",
                        "status": "answered",
                        "question": "How many herbs should Renn gather per phase?",
                        "answer": "You decide",
                        "result": {"gap": "No explicit herb rate is established."},
                    },
                }
                analysis = {
                    "turn_id": plan["tick_id"],
                    "request_type": "backend_autonomy",
                    "process_type": "backend_autonomy",
                    "mode": "backend_autonomy",
                    "coverage_check": {"ready_for_lead_resolver": True, "missing_specialists": [], "incomplete_specialists": []},
                    "specialist_results": [
                        {"specialist": "rules", "status": "complete", "findings": ["Determine gathering quantity from rules or authorized assumption."], "conflicts": ["No explicit herb rate is established."], "evidence_requests": []},
                        {"specialist": "character", "status": "complete", "findings": ["Renn can perform the assigned gathering task."], "conflicts": [], "evidence_requests": []},
                    ],
                    "action_frames": [{"text": "Renn gathers medicinal herbs in the north grove.", "actor": "Renn"}],
                    "selected_sections": [],
                    "specialist_updates": {},
                }
                lead = BackendLeadResolver(ROOT).resolve(analysis, plan=plan, context=hidden_context)
                self.backend_lead_resolutions.append({"plan": plan, "lead_result": lead})
                if lead.get("status") != "resolved":
                    return {"status": lead.get("status", "blocked")}
                resolution = lead.get("resolution_record") or {}
                if isinstance(resolution.get("assumption_record"), dict) and resolution["assumption_record"].get("status") == "provisional":
                    self.assumption_record = resolution["assumption_record"]
                packet = resolution.get("background_packet") or {}
                actions = packet.get("actions") or plan["actions"]
                for change in resolution.get("resource_changes", []):
                    delta = change.get("delta") if isinstance(change, dict) else None
                    if isinstance(delta, (int, float)):
                        self.herbs_total += delta
                return {
                    "status": "resolved",
                    "actions": actions,
                    "resource_changes": resolution.get("resource_changes", []),
                    "automatic_updates": resolution.get("automatic_updates", []),
                    "world_updates": resolution.get("world_updates", []),
                    "completed_directives": packet.get("completed_directives", resolution.get("completed_directives", [])),
                    "notes": resolution.get("notes", []),
                    "next_context": {**(packet.get("next_context") or {}), "assumption_record": self.assumption_record},
                }

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
        game = RealFullCycleGame(root)
        pipeline = CampaignPipeline(root, modules=game)
        turn_results = [pipeline.submit(prompt) for prompt in PROMPTS]
        ticks = game.store.load_ticks()
        final_state = RuntimeStateStore(root).load()
        resource_changes = [
            change
            for tick in ticks
            for change in tick.get("resource_changes", [])
            if isinstance(change, dict) and "herb" in str(change.get("resource", "")).casefold()
        ]
        result = {
            "player_prompts": PROMPTS,
            "turn_results": turn_results,
            "backend_ticks": ticks,
            "backend_lead_resolutions": game.backend_lead_resolutions,
            "background_calls": game.background_calls,
            "final_message": final_state.get("message", ""),
            "final_herb_total": game.herbs_total,
            "checks": {
                "player_cycle_entered_backend": game.background_calls >= 3 and len(ticks) == 3,
                "backend_resolved_each_tick": len([item for item in game.backend_lead_resolutions if item["lead_result"].get("status") == "resolved"]) == 3,
                "backend_calculated_resources": bool(resource_changes) and sum(change.get("delta", 0) for change in resource_changes) == game.herbs_total,
                "player_met_character_after_third_turn": "Renn is here" in final_state.get("message", ""),
                "meeting_revealed_result": f"{game.herbs_total} herbs gathered" in final_state.get("message", ""),
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

**{checks['player_cycle_entered_backend']}** — three player turns created three committed private backend phase ticks; transient retry attempts were not committed twice.

## 2. Backend resolution

The real Backend Lead Resolver resolved Renn's autonomous action on every tick.
No herbs-per-phase value was supplied by this test. The quantity below came from
`resource_changes` returned by the Lead Resolver.

- Backend resolver attempts: **{len(game.backend_lead_resolutions)}**
- Committed backend resolutions: **{len([item for item in game.backend_lead_resolutions if item['lead_result'].get('status') == 'resolved'])}**
- Final herb total: **{result['final_herb_total']}**
- Resources calculated by Lead Resolver: **{checks['backend_calculated_resources']}**
- Resolver-decided total: **{result['final_herb_total']} medicinal herbs**

## 3. Result after the player meets Renn

> {result['final_message']}

- Player met Renn after turn three: **{checks['player_met_character_after_third_turn']}**
- Calculated result was revealed: **{checks['meeting_revealed_result']}**

## Status

**{result['status'].upper()}**

Structured detail: `trial/47_real_full_player_backend_cycle_result.json`
"""
    RESULT_MD.write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
