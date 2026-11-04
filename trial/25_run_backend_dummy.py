"""Exercise every background backend component with deterministic dummy data."""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.autonomy_resolver import AutonomyResolver
from backend.background_state import BackgroundStateStore
from backend.contracts import BackgroundDirective, PhasePosition
from backend.phase_clock import PhaseClock
from backend.phase_tick import PhaseTickEngine
from backend.visibility_filter import VisibilityFilter

DATA_PATH = ROOT / "trial" / "25_backend_dummy_data.json"
TEMP_PATH = ROOT / "trial" / "25_backend_temp_memory.md"
PRIVATE_PATH = ROOT / "trial" / "25_backend_private_state.json"
RESULT_PATH = ROOT / "trial" / "25_backend_dummy_result.json"


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    TEMP_PATH.write_text("# Dummy Experimentation Register\n", encoding="utf-8")
    PRIVATE_PATH.unlink(missing_ok=True)
    store = BackgroundStateStore(TEMP_PATH, private_state_path=PRIVATE_PATH)
    directives = [BackgroundDirective.from_dict(item) for item in data["directives"]]
    for directive in directives:
        store.upsert_directive(directive)

    clock = PhaseClock()
    start = clock.position(data["start"]["day"], data["start"]["phase"])
    transitions = clock.advance(start, data["phases_elapsed"])

    autonomy = AutonomyResolver()
    planned_actions = autonomy.plan(
        store.load_directives(),
        transitions[0].current,
        character_state=data["character_state"],
        tick_id=transitions[0].tick_id,
    )

    analyzer_started = []
    analyzer_lock = threading.Lock()

    def analyze(name, plan, context):
        with analyzer_lock:
            analyzer_started.append(name)
        time.sleep(0.02)
        result = {
            "specialist": name,
            "status": "complete",
            "finding": f"Dummy {name} analysis for {plan['tick_id']}"
        }
        if name == "cache":
            result["cache_delta"] = {
                "durable_facts": [], "active_threads": [], "pending_commitments": [],
                "unresolved_questions": [], "expiring_facts": [],
            }
        return result

    def resolve_tick(plan):
        return {
            "status": "resolved",
            "actions": [
                {
                    **action,
                    "status": "successful" if action["actor"] == "Seris" else "idle",
                    "player_visibility": "hidden",
                    "ooc_visibility": action.get("ooc_visibility", "private")
                }
                for action in plan["actions"]
            ],
            "automatic_updates": [
                {
                    "state": "current MP",
                    "before": 95,
                    "delta": 5,
                    "after": 100,
                    "visibility": "visible",
                    "ooc_visibility": "teammate_status"
                }
            ],
            "resource_changes": [
                {
                    "resource": "arrows",
                    "before": 20,
                    "delta": -3,
                    "after": 17,
                    "reason": "Seris hunted a monster",
                    "visibility": "hidden",
                    "ooc_visibility": "teammate_status"
                }
            ],
            "world_updates": [
                {
                    "description": "Monster tracks were found near the eastern road",
                    "visibility": "visible",
                    "ooc_visibility": "private"
                }
            ],
            "visibility_events": [],
            "completed_directives": [],
            "notes": ["Dummy resolution; hidden NPC action remains in session state."]
        }

    engine = PhaseTickEngine(store, clock=clock, autonomy=autonomy)
    engine_result = engine.run(
        start,
        data["phases_elapsed"],
        context={"character_state": data["character_state"]},
        analyze=analyze,
        resolve_tick=resolve_tick,
    )
    committed_record = engine_result["ticks"][0]["record"]
    player_view = VisibilityFilter().for_narrator(committed_record)

    # Verify idempotence: rerunning the same phase does not apply it twice.
    retry = engine.run(
        start,
        data["phases_elapsed"],
        context={"character_state": data["character_state"]},
        resolve_tick=resolve_tick,
    )

    result = {
        "phase_clock": {
            "start": start.to_dict(),
            "transitions": [item.to_dict() for item in transitions],
            "status": "passed" if transitions[0].current.phase == "Evening" else "failed",
        },
        "background_state": {
            "loaded_directives": [item.to_dict() for item in store.load_directives()],
            "public_register_path": str(TEMP_PATH),
            "private_state_path": str(PRIVATE_PATH),
            "status": "passed" if len(store.load_directives()) == 2 and PRIVATE_PATH.exists() else "failed",
        },
        "autonomy_resolver": {
            "planned_actions": [item.to_dict() for item in planned_actions],
            "status": "passed" if any("Scout the road" in item.chosen_action for item in planned_actions) and any("Remain idle" in item.chosen_action for item in planned_actions) else "failed",
        },
        "phase_tick_engine": {
            "result": engine_result,
            "specialists_started": analyzer_started,
            "status": "passed" if len(analyzer_started) == 5 and engine_result["status"] == "complete" else "failed",
        },
        "visibility_filter": {
            "player_view": player_view,
            "hidden_action_removed": not any(item.get("actor") == "Seris" for item in player_view["actions"]),
            "private_world_update_withheld": not player_view["world_updates"],
            "status": "passed" if player_view["hidden_event_count"] >= 3 else "failed",
        },
        "idempotence": {
            "retry": retry,
            "status": "passed" if retry["ticks"][0]["status"] == "already_committed" else "failed",
        },
        "private_storage": {
            "world_surprise_retained_privately": "Monster tracks were found near the eastern road" in PRIVATE_PATH.read_text(encoding="utf-8"),
            "world_surprise_not_mirrored": "Monster tracks were found near the eastern road" not in TEMP_PATH.read_text(encoding="utf-8"),
            "status": "passed" if "Monster tracks were found near the eastern road" in PRIVATE_PATH.read_text(encoding="utf-8") and "Monster tracks were found near the eastern road" not in TEMP_PATH.read_text(encoding="utf-8") else "failed",
        },
        "temp_memory": TEMP_PATH.read_text(encoding="utf-8"),
    }
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
