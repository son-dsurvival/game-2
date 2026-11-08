"""Discover recurring campaign domains from all available campaign data.

Discovery is deliberately separate from unlocking. This module can identify a
candidate branch, but a resolved Lead Resolver result plus the normal approval
path is still required before a branch becomes routable.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class BranchPattern:
    name: str
    specialist: str
    activation_tags: tuple[str, ...]
    aliases: tuple[str, ...]
    description: str
    lore_only_is_not_establishment: bool = True


# This catalog describes domains that can grow into recurring stateful branches.
# It is not the unlock registry: a mention creates evidence, never permission.
BRANCH_PATTERNS: tuple[BranchPattern, ...] = (
    BranchPattern("business", "business", ("activity.business",), ("business", "trade", "market", "shop", "contract", "commerce"), "trade, markets, contracts, and enterprise"),
    BranchPattern("alchemy", "alchemy", ("activity.alchemy",), ("alchemy", "reagent", "potion", "transmute", "formula"), "alchemy processes, recipes, and reagents"),
    BranchPattern("politics", "politics", ("activity.politics", "context.factional"), ("politics", "faction", "office", "influence", "diplomacy", "treaty"), "factions, offices, diplomacy, and political power"),
    BranchPattern("class", "class", ("context.class_system",), ("class", "classless", "class xp", "class progression", "skill path"), "class choice and class progression"),
    BranchPattern("relay", "relay", ("context.relay_system",), ("relay", "linked cognition", "network awareness", "telepathy"), "relay and linked-network mechanics"),
    BranchPattern("world", "world", ("activity.exploration", "mechanic.world_event"), ("world event", "event trigger", "number pool", "d100", "monster tide", "dungeon"), "scheduled world events and world-state changes"),
    BranchPattern("consequences", "consequences", ("stakes.irreversible", "stakes.contested"), ("irreversible", "permanent consequence", "contested", "factional consequence", "world consequence"), "persistent and irreversible consequences"),
    BranchPattern("dungeon_ecology", "dungeon_ecology", ("activity.exploration", "context.environmental"), ("monster dungeon", "monster tide", "dungeon pressure", "dungeon production", "dungeon ecology"), "dungeons, production pressure, monster populations, and tides"),
    BranchPattern("peoples", "peoples", ("context.factional", "context.social"), ("dungeonborn", "awakened earthborn", "constructed life", "anomalous life", "new people", "species recognition"), "peoples, species recognition, and inter-peoples relations"),
    BranchPattern("civilization", "civilization", ("context.civilization", "activity.base_development"), ("civilization", "base core", "village", "town", "kingdom", "empire", "five-branch pyramid"), "Bases and civilization hierarchy"),
    BranchPattern("religion", "religion", ("context.religious", "context.tier6"), ("tier-6 cult", "tier-6 church", "champion", "blessing", "followers", "communion"), "Tier-6 entities, religions, blessings, and champions"),
    BranchPattern("technology", "technology", ("activity.engineering", "context.technology"), ("mana-integrated", "mana technology", "evolved vehicle", "power grid", "artificial intelligence", "engineering path"), "technology, engineering, and mana integration"),
    BranchPattern("knowledge", "knowledge", ("activity.study", "context.knowledge"), ("knowledge catalog", "skill manual", "license", "library", "training hall", "system instruction"), "knowledge markets, study, and instructional institutions"),
)

_PATTERN_BY_NAME = {item.name: item for item in BRANCH_PATTERNS}


def _flatten(value: Any, *, prefix: str = "runtime") -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(f"{prefix}.{key}: {_flatten(item, prefix=f'{prefix}.{key}')}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return "\n".join(_flatten(item, prefix=prefix) for item in value)
    return str(value)


def _matches(text: str, pattern: BranchPattern) -> list[str]:
    lowered = text.casefold()
    hits = []
    for alias in pattern.aliases:
        # Avoid substring collisions such as world `dungeon` matching
        # `Dungeonborn`; aliases represent words or phrases, not stems.
        expression = r"(?<![A-Za-z0-9_])" + re.escape(alias.casefold()) + r"(?![A-Za-z0-9_])"
        if re.search(expression, lowered):
            hits.append(alias)
    return list(dict.fromkeys(hits))


class BranchDiscovery:
    """Read campaign evidence and return explainable branch candidates."""

    def __init__(self, repo_root: str | Path = "."):
        self.root = Path(repo_root).resolve()

    def discover(self, runtime_data: Any = None, *, persist: bool = True) -> dict[str, Any]:
        registry = self._registry()
        sources = self._sources(runtime_data)
        candidates = []
        for pattern in BRANCH_PATTERNS:
            if pattern.name in registry and str(registry[pattern.name].get("status", "locked")).casefold() == "unlocked":
                continue
            hits = []
            source_groups: set[str] = set()
            lore_hits = []
            active_hits = []
            for source_name, text, kind in sources:
                found = _matches(text, pattern)
                if not found:
                    continue
                if kind == "registry":
                    continue
                item = {"source": source_name, "kind": kind, "signals": found[:8]}
                hits.append(item)
                source_groups.add(kind)
                if kind == "lore":
                    lore_hits.append(item)
                elif kind in {"active_record", "runtime_state", "current_turn", "resolved_turn"}:
                    active_hits.append(item)
            if not hits:
                continue
            # Lore describes possibilities; live evidence establishes branches.
            # Two independent active groups indicate recurrence. A resolved
            # branch claim is still marked as confirmation-required below.
            recurring = len({item["source"] for item in active_hits}) >= 2 or len(active_hits) >= 3
            current_turn = any(item["kind"] in {"current_turn", "resolved_turn"} for item in active_hits)
            established_evidence = recurring or (current_turn and len(active_hits) >= 1)
            candidates.append({
                "branch": pattern.name,
                "specialist": pattern.specialist,
                "activation_tags": list(pattern.activation_tags),
                "description": pattern.description,
                "signals": hits,
                "lore_only": bool(lore_hits) and not active_hits,
                "source_groups": sorted(source_groups),
                "recurring": recurring,
                "established_evidence": established_evidence,
                "status": "candidate" if established_evidence else "lore_candidate",
                "requires_lead_confirmation": True,
                "unlockable": pattern.name not in registry or str(registry[pattern.name].get("status", "locked")).casefold() != "unlocked",
            })
        candidates.extend(self._proposal_candidates(runtime_data, registry))
        report = {
            "status": "complete",
            "sources_scanned": [name for name, _text, _kind in sources],
            "candidates": candidates,
            "unlock_candidates": [item for item in candidates if item["established_evidence"]],
            "note": "Discovery proposes evidence-backed candidates; only a resolved and approved branch change unlocks routing.",
        }
        if persist:
            try:
                from brain.branch_registry import BranchRegistry
            except ImportError:
                from branch_registry import BranchRegistry
            report["persisted_candidates"] = BranchRegistry(self.root).record_candidates(candidates)
        else:
            report["persisted_candidates"] = []
        return report

    def _proposal_candidates(self, runtime_data: Any, registry: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        """Surface safe Create Specialist proposals as candidates, never unlocks."""
        if not isinstance(runtime_data, dict):
            return []
        found: list[dict[str, Any]] = []
        proposal_items: list[dict[str, Any]] = []
        for container in self._walk_dicts(runtime_data):
            proposed = container.get("created_specialists")
            if isinstance(proposed, list):
                proposal_items.extend(item for item in proposed if isinstance(item, dict))
        for item in proposal_items:
            name = item.get("name")
            if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", name):
                continue
            if name in _PATTERN_BY_NAME or name in registry:
                continue
            if not isinstance(item.get("purpose"), str) or not item.get("purpose", "").strip():
                continue
            tags = item.get("activation_tags", [])
            if not isinstance(tags, list):
                continue
            found.append({
                "branch": name,
                "specialist": name,
                "activation_tags": [str(tag) for tag in tags if str(tag).strip()],
                "description": item["purpose"].strip(),
                "signals": [{"source": "runtime.created_specialists", "kind": "active_record", "signals": [name]}],
                "lore_only": False,
                "source_groups": ["active_record"],
                "recurring": False,
                "established_evidence": False,
                "status": "proposal_candidate",
                "requires_lead_confirmation": True,
                "unlockable": True,
            })
        return found

    @staticmethod
    def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from BranchDiscovery._walk_dicts(child)
        elif isinstance(value, list):
            for child in value:
                yield from BranchDiscovery._walk_dicts(child)

    def supports(self, branch: str, runtime_data: Any = None) -> bool:
        result = self.discover(runtime_data, persist=False)
        return any(item["branch"] == branch and item["established_evidence"] for item in result["candidates"])

    def _registry(self) -> dict[str, dict[str, Any]]:
        try:
            from brain.branch_registry import BranchRegistry
        except ImportError:
            from branch_registry import BranchRegistry
        return BranchRegistry(self.root).entries()

    def _sources(self, runtime_data: Any) -> list[tuple[str, str, str]]:
        sources: list[tuple[str, str, str]] = []
        markdown_root = self.root / "markdown_files"
        if markdown_root.is_dir():
            for path in sorted(markdown_root.glob("*.md")):
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                name = path.name
                if name == "Branch Registry.md":
                    kind = "registry"
                else:
                    kind = "lore" if "WORLD" in name.upper() or "rules" in name.casefold() else "active_record"
                    if name in {"TEMP_MEMORY.md", "Experimentation Register.md"} or "log" in name.casefold() or "register" in name.casefold():
                        kind = "active_record"
                sources.append((f"markdown_files/{name}", text, kind))
                # The world-frame file also carries mutable Event log/Game log
                # sections. Treat those sections as active evidence rather than
                # as hypothetical lore.
                if "WORLD" in name.upper():
                    for heading in ("Event log", "Game log"):
                        match = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.I | re.M)
                        if match:
                            tail = text[match.end():]
                            next_heading = re.search(r"^##\s+", tail, re.M)
                            section = tail[:next_heading.start()] if next_heading else tail
                            sources.append((f"markdown_files/{name}::{heading}", section, "active_record"))
        state_root = self.root / "brain" / "state"
        if state_root.is_dir():
            for path in sorted(state_root.glob("*.json")):
                # Model-call journals contain provider prompts and are not
                # campaign evidence; session/background/cache JSON is.
                if path.name == "model_calls.jsonl":
                    continue
                try:
                    sources.append((f"brain/state/{path.name}", path.read_text(encoding="utf-8"), "runtime_state"))
                except OSError:
                    pass
        if runtime_data is not None:
            if isinstance(runtime_data, dict):
                for key in ("resolved_turn", "lead_resolver", "resolution_record", "specialist_results", "game_cache", "conversation_history", "history", "resolved_turns", "day_end_records", "player_input", "player_message", "message", "chat_context", "evidence_bundle"):
                    if key not in runtime_data:
                        continue
                    if key == "evidence_bundle":
                        kind = "reference"
                        sources.append(("runtime.evidence_bundle", _flatten(runtime_data[key], prefix=key), kind))
                        nested = runtime_data[key] if isinstance(runtime_data[key], dict) else {}
                        for nested_key in ("player_input", "conversation_history", "game_cache"):
                            if nested_key in nested:
                                nested_kind = "active_record" if nested_key == "game_cache" else "current_turn"
                                sources.append((f"runtime.evidence_bundle.{nested_key}", _flatten(nested[nested_key], prefix=nested_key), nested_kind))
                        continue
                    elif key in {"resolved_turn", "lead_resolver", "resolution_record"}:
                        kind = "resolved_turn"
                    elif key in {"game_cache", "specialist_results", "history", "resolved_turns", "day_end_records"}:
                        kind = "active_record"
                    else:
                        kind = "current_turn"
                    sources.append((f"runtime.{key}", _flatten(runtime_data[key], prefix=key), kind))
            else:
                sources.append(("runtime_input", _flatten(runtime_data), "current_turn"))
        return sources


def discover_branches(repo_root: str | Path = ".", runtime_data: Any = None) -> dict[str, Any]:
    return BranchDiscovery(repo_root).discover(runtime_data)
