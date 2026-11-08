"""Verify branch discovery scans lore, logs, cache, and current conversation."""
from __future__ import annotations
import json, tempfile, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from brain.branch_discovery import BranchDiscovery
from brain.branch_registry import BranchRegistry

def main():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        md = root / "markdown_files"
        md.mkdir(parents=True)
        (md / "Branch Registry.md").write_text("# Branch Registry\n\n## Unlock Rules\n", encoding="utf-8")
        (md / "🌍 CORE WORLD FRAME (REFINED).md").write_text(
            "# Lore\nDungeonborn peoples, civilization bases, and Tier-6 religions are possible future developments.\n\n"
            "## Event log\nNo resolved world events recorded.\n\n## Game log\nNo player-facing game turns recorded.\n", encoding="utf-8")
        (md / "TEMP_MEMORY.md").write_text(
            "## Game Cache\n- Dungeonborn diplomacy is an active thread.\n\n"
            "## Event log\nA Dungeonborn settlement was encountered and its council requested a treaty.\n", encoding="utf-8")
        result = BranchDiscovery(root).discover({
            "player_input": "I negotiate a treaty with the Dungeonborn council.",
            "conversation_history": ["We have been dealing with the settlement for several turns."],
            "game_cache": {"active_threads": ["Dungeonborn diplomacy"]},
        }, persist=False)
        by_name = {item["branch"]: item for item in result["candidates"]}
        persisted = BranchRegistry(root).record_candidates(result["candidates"])
        registry = BranchRegistry(root)
        checks = {
            "peoples_detected": "peoples" in by_name,
            "peoples_established": by_name.get("peoples", {}).get("established_evidence") is True,
            "peoples_not_auto_unlocked": by_name.get("peoples", {}).get("status") == "candidate",
            "civilization_lore_candidate": by_name.get("civilization", {}).get("status") == "lore_candidate",
            "world_empty_log_not_established": by_name.get("world", {}).get("established_evidence") is not True,
            "requires_confirmation": all(item.get("requires_lead_confirmation") for item in result["candidates"]),
            "candidate_persisted": registry.entry("peoples").get("status") == "candidate",
            "candidate_not_routed": not registry.is_unlocked("peoples"),
            "persistence_changed": "peoples" in persisted,
        }
        if not all(checks.values()):
            raise AssertionError(checks)
        output = {"status": "passed", **checks, "unlock_candidates": result["unlock_candidates"]}
        target = Path(__file__).with_name("31_branch_discovery_result.json")
        target.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
