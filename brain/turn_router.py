"""Turn Router for the campaign runtime.

This is the first deterministic implementation of the Turn Router described in
``plan.txt``.  It deliberately does not resolve actions, roll dice, mutate files,
or determine consequences.  It only performs pre-routing checks, creates
multi-label tags, selects specialists, and plans evidence requests.

The router supports two classifiers:

* a dependency-free heuristic classifier for local/offline development;
* a DeepSeek classifier through the OpenAI-compatible API.

DeepSeek is used only to interpret the player's intent.  The Python code still
owns preflight gates, tag validation, specialist routing, evidence planning, and
all state boundaries.  API credentials are read from the process environment
(or an existing .env file) and are never printed or modified.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from brain.branch_registry import BranchRegistry
    from brain.model_gateway import ModelGateway
except ModuleNotFoundError:  # Direct execution: python brain/turn_router.py
    from branch_registry import BranchRegistry
    from model_gateway import ModelGateway


# Core analysis categories always exist. Evidence Bundle construction and the
# Recorder handle context/memory; Create and leaf domains are routed as needed.
MANDATORY_SPECIALISTS = ["rules", "character", "special"]
TAXONOMY_PATH = (
    Path(__file__).resolve().parent
    / "info"
    / "router_taxonomy"
    / "tags.json"
)


def _fallback_taxonomy() -> dict[str, Any]:
    """Provide a small safe taxonomy when the generated taxonomy is empty.

    The checked-in taxonomy normally comes from the campaign index. Keeping a
    fallback here means specialist routing still works in a fresh checkout (or
    while indexes are being rebuilt); it is intentionally conservative.
    """
    def tag(category: str, description: str, indicators: tuple[str, ...], specialists: tuple[str, ...]) -> dict[str, Any]:
        return {
            "category": category,
            "description": description,
            "positive_indicators": list(indicators),
            "specialists": list(specialists),
        }

    return {"tags": {
        "mode.combat": tag("mode", "The action is combat", ("attack", "fight", "combat", "duel"), ()),
        "mode.noncombat": tag("mode", "The action is not combat", (), ()),
        "activity.combat": tag("activity", "A hostile combat action", ("attack", "fight", "strike"), ("combat", "rules", "character")),
        "activity.exploration": tag("activity", "Exploration or investigation", ("explore", "search", "investigate", "ruin"), ("world", "special")),
        "activity.experiment": tag("activity", "An experiment or practice action", ("experiment", "test", "practice", "refine"), ("experimentation", "rules")),
        "activity.business": tag("activity", "Business or trade activity", ("business", "trade", "market", "contract"), ("business", "special")),
        "activity.alchemy": tag("activity", "Alchemy or potion activity", ("alchemy", "potion", "reagent", "transmute"), ("alchemy", "special")),
        "activity.politics": tag("activity", "Politics or faction activity", ("politics", "faction", "influence", "office"), ("politics", "special")),
        "mechanic.difficulty": tag("mechanic", "A task difficulty or roll target", ("difficulty", "target", "roll"), ("difficulty", "rules")),
        "mechanic.resource_cost": tag("mechanic", "Resources, materials, or mana", ("resource", "mana", "cost", "spend", "material"), ("resources", "rules")),
        "mechanic.time_cost": tag("mechanic", "Time, phase, or duration", ("time", "phase", "wait", "day"), ("time", "rules")),
        "mechanic.cognitive_assistance": tag("mechanic", "Cognitive assistance", ("assist", "advice", "memory", "telepathy"), ("cognitive_assistance", "character")),
        "mechanic.modifier_creation": tag("mechanic", "Creating or refining a stat or effect modifier", ("new modifier", "gain a modifier", "develop a technique", "refine a modifier", "breakthrough", "repeated success", "training breakthrough"), ("create_stat_modifier", "create_effect_modifier")),
        "mechanic.spell_creation": tag("mechanic", "Spell creation or magic", ("spell", "magic", "cast"), ("spell", "rules", "special")),
        "context.emotional": tag("context", "Emotional or relationship context", ("relationship", "trust", "love", "consent"), ("relationship", "character")),
        "context.class_system": tag("context", "Class or class progression", ("class", "skill", "level"), ("class", "special")),
        "context.relay_system": tag("context", "Relay or network system", ("relay", "network", "linked"), ("relay", "special")),
        "participant.companion": tag("participant", "A companion or NPC participates", ("companion", "ally", "npc"), ("npc_autonomy", "character")),
        "stakes.irreversible": tag("stakes", "An irreversible or permanent stake", ("permanent", "irreversible", "dangerous"), ("consequences", "special")),
        "stakes.contested": tag("stakes", "The action is contested", ("opposed", "contest", "enemy"), ("consequences", "rules")),
        "stakes.low": tag("stakes", "No high-risk marker was found", (), ()),
    }}


def _load_taxonomy() -> dict[str, Any]:
    """Load and minimally validate the external routing taxonomy."""
    try:
        with TAXONOMY_PATH.open("r", encoding="utf-8") as handle:
            taxonomy = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return _fallback_taxonomy()

    tags = taxonomy.get("tags") if isinstance(taxonomy, dict) else None
    required = {"category", "description", "positive_indicators", "specialists"}
    if not isinstance(tags, dict) or not tags:
        return _fallback_taxonomy()
    if any(not isinstance(definition, dict) or not required.issubset(definition) for definition in tags.values()):
        return _fallback_taxonomy()
    return taxonomy


ROUTER_TAXONOMY = _load_taxonomy()
TAG_DEFINITIONS: dict[str, dict[str, Any]] = ROUTER_TAXONOMY["tags"]
ALLOWED_TAGS = frozenset(TAG_DEFINITIONS)
ALLOWED_MODES = {
    tag.removeprefix("mode.")
    for tag, definition in TAG_DEFINITIONS.items()
    if definition.get("category") == "mode"
}
SPECIALISTS_BY_TAG = {
    tag: list(definition.get("specialists", []))
    for tag, definition in TAG_DEFINITIONS.items()
}

# These former one-topic roles are now responsibilities of the always-on core
# lanes. They remain valid registry names for replay and explicit CLI runs, but
# normal routing must not create a second serial-looking specialist chain.
CORE_OWNED_SPECIALISTS = {
    "canon": "character",
    "current_state": "character",
    "combat": "rules",
    "difficulty": "rules",
    "experimentation": "rules",
    "resources": "rules",
    "time": "rules",
    "xp": "rules",
    "spell": "rules",
    "relationship": "character",
    "npc_autonomy": "character",
    "modifier": "character",
    "cognitive_assistance": "character",
    "modifier_creation": "create_effect_modifier",
    "create_stat_modifier": "create_stat_modifier",
    "create_effect_modifier": "create_effect_modifier",
}


def _taxonomy_prompt_text() -> str:
    return "\\n".join(
        f"- {tag}: {definition['description']}"
        for tag, definition in sorted(TAG_DEFINITIONS.items())
    )


DEEPSEEK_ROUTER_PROMPT = """You are the semantic Turn Router for a tabletop campaign.
Return JSON only. Do not resolve success, damage, costs, relationships, dice, or
consequences. Identify intent and route analysis only.

Use only these modes: combat, noncombat, mixed.
Use only the allowed tags supplied below. Tags may combine across categories,
but mode must be exactly one value. Split multiple declared actions into segments.
Mark clarification_required when the player's intent is materially ambiguous.
Every tag must include a short evidence quote from the player message. Copy tag
identifiers exactly from the Allowed tags list. Do not use category names,
shortened names, mode names, or synonyms inside segment tags.

Allowed tags:
{allowed_tags}

Required JSON shape:
{{
  "mode": "combat|noncombat|mixed",
  "segments": [
    {{"text": "...", "classification": "...", "tags": ["..."]}}
  ],
  "tags": [
    {{"tag": "...", "evidence": "..."}}
  ],
  "clarification_required": false,
  "clarification_questions": []
}}
"""

EVIDENCE_REQUESTS = {
    "activity.experiment": {
        "required_sources": ["game rules (1).md", "Experimentation Register.md"],
        "required_headings": ["Outcome-Based Practice Carryover", "Derived Refinement"],
    },
    "context.emotional": {
        "required_sources": ["character relationship.md", "TEMP_MEMORY.md"],
        "required_headings": ["Relationship Score", "Relationship Dynamics"],
    },
    "participant.companion": {
        "required_sources": ["character relationship.md", "TEMP_MEMORY.md"],
        "required_headings": ["NPC Autonomy", "Companion"],
    },
    "activity.exploration": {
        "required_sources": ["🌍 CORE WORLD FRAME (REFINED).md", "status sheet.md"],
        "required_headings": ["Exploration", "Current Campaign State"],
    },
    "mechanic.resource_cost": {
        "required_sources": ["Ledger Resources.md", "game rules (1).md"],
        "required_headings": ["Current Resources", "Resource Costs"],
    },
    "mechanic.time_cost": {
        "required_sources": ["status sheet.md", "game rules (1).md"],
        "required_headings": ["Current Campaign State", "Action Time"],
    },
    "mode.combat": {
        "required_sources": ["game rules (1).md", "status sheet.md"],
        "required_headings": ["Combat", "Current Campaign State"],
    },
    "mechanic.cognitive_assistance": {
        "required_sources": ["game rules (1).md", "character relationship.md"],
        "required_headings": ["Cognitive Assistance", "NPC Autonomy"],
    },
    "mechanic.modifier_creation": {
        "required_sources": ["game rules (1).md", "Experimentation Register.md", "TEMP_MEMORY.md", "status sheet.md"],
        "required_headings": ["Stat Modifiers", "Effect Modifier", "Completed Experiments", "Game Cache", "Status Sheet Modifier Index"],
    },
    "mechanic.world_event": {
        "required_sources": ["🌍 CORE WORLD FRAME (REFINED).md", "TEMP_MEMORY.md"],
        "required_headings": ["World Events", "Session Canon"],
    },
    "context.class_system": {
        "required_sources": ["status sheet.md", "game rules (1).md"],
        "required_headings": ["CLASS", "Class"],
    },
    "context.relay_system": {
        "required_sources": ["Ledger Resources.md", "game rules (1).md"],
        "required_headings": ["Cognitive Relay Space", "Relay Building", "Relay"],
    },
    "activity.business": {
        "required_sources": ["Ledger Resources.md", "game rules (1).md"],
        "required_headings": ["Finances and Business", "Business", "Trade"],
    },
}


@dataclass
class TagEvidence:
    tag: str
    source: str
    evidence: str
    status: str = "active"


@dataclass
class ActionSegment:
    segment_id: int
    text: str
    tags: list[str] = field(default_factory=list)
    classification: str = "unknown"


@dataclass
class RoutingRecord:
    turn_id: str
    request_type: str
    process_type: str
    mode: str | None
    segments: list[ActionSegment]
    tags: list[TagEvidence]
    required_specialists: list[str]
    evidence_requests: list[dict[str, Any]]
    preflight: dict[str, Any]
    clarification_required: bool = False
    clarification_questions: list[str] = field(default_factory=list)
    evidence_status: str = "pending"
    admin_request: dict[str, Any] | None = None
    routing_version: int = 1
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TurnRouter:
    """Create an immutable routing decision without resolving the turn."""

    def __init__(self, repo_root: str | Path = ".", require_git: bool = True):
        self.repo_root = Path(repo_root).resolve()
        self.require_git = require_git
        self.branch_registry = BranchRegistry(self.repo_root)

    def route(
        self,
        player_message: str,
        *,
        campaign_mode: bool,
        current_phase: str | None = None,
        current_state: dict[str, Any] | None = None,
        active_npcs: Iterable[str] = (),
        temporary_memory: Iterable[str] = (),
        turn_active: bool = False,
        classifier: str = "auto",
    ) -> RoutingRecord:
        preflight = self._preflight(
            player_message=player_message,
            campaign_mode=campaign_mode,
            turn_active=turn_active,
        )

        request_type = self._request_type(player_message, preflight)
        admin_request = self._admin_request(player_message) if request_type == "admin" else None

        # Commands, out-of-game requests, and blocked turns never reach an LLM.
        # They are handled entirely by deterministic preflight logic.
        if preflight["message_kind"] != "normal_action" or preflight["errors"]:
            tags: list[TagEvidence] = []
            mode: str | None = None
            classified_segments: list[ActionSegment] | None = [
                ActionSegment(1, player_message.strip(), [], preflight["message_kind"])
            ]
            classification_source = "preflight"
            model_questions: list[str] = []
        else:
            (
                tags,
                mode,
                classified_segments,
                classification_source,
                model_questions,
            ) = self._classify_message(
                player_message,
                classifier=classifier,
                current_phase=current_phase,
                current_state=current_state or {},
                active_npcs=active_npcs,
                temporary_memory=temporary_memory,
            )

        segments = classified_segments or self._segment_actions(player_message, tags, mode)
        if classified_segments is not None:
            known_tags = {item.tag for item in tags}
            for segment in segments:
                segment.tags = [tag for tag in segment.tags if tag in known_tags]
                if not segment.tags:
                    segment.tags = sorted(known_tags)
        preflight["classifier"] = classification_source
        tags.extend(self._unlocked_branch_tags(player_message))
        tags = list({item.tag: item for item in tags}.values())
        process_type = self._process_type(player_message, preflight, tags)

        specialists = set(MANDATORY_SPECIALISTS)
        tag_names = {tag.tag for tag in tags}
        for tag in tag_names:
            for specialist in SPECIALISTS_BY_TAG.get(tag, []):
                # The broad core lane owns these responsibilities now. A
                # branch-specific specialist is routed only after its branch is
                # explicitly unlocked in Branch Registry.md or pending session
                # updates. A tag alone is not an unlock.
                owner = CORE_OWNED_SPECIALISTS.get(specialist)
                if owner:
                    specialists.add(owner)
                elif self.branch_registry.is_unlocked(specialist):
                    specialists.add(specialist)
        # Custom branches may not exist in the static taxonomy yet. Their
        # registry activation tags still route their unlocked specialist.
        specialists.update(self.branch_registry.specialists_for_tags(tag_names))

        if process_type == "in_world_discussion":
            # Discussion is a process, not a generic action. Do not run the
            # category placeholders; activate only character/social leaf roles
            # and any explicitly relevant unlocked branch specialist.
            specialists = self._discussion_specialists(
                player_message, tag_names, active_npcs, specialists
            )

        evidence_requests = self._build_evidence_requests(tags)
        clarification_questions = self._clarification_questions(tags, mode, segments)
        # DeepSeek may identify ambiguity more accurately than the heuristic
        # fallback.  The model's questions are preserved through the classifier
        # result when available; mechanical ambiguity checks remain local.
        clarification_required = bool(clarification_questions)
        if model_questions:
            clarification_questions = list(dict.fromkeys(
                [*model_questions, *clarification_questions]
            ))
            clarification_required = True

        # A failed preflight must not accidentally look like a resolvable turn.
        if preflight["errors"]:
            evidence_status = "blocked_by_preflight"
        elif clarification_required:
            evidence_status = "clarification_required"
        else:
            evidence_status = "pending"

        return RoutingRecord(
            turn_id=self._new_turn_id(current_phase),
            request_type=request_type,
            process_type=process_type,
            mode=mode,
            segments=segments,
            tags=tags,
            required_specialists=sorted(specialists),
            evidence_requests=evidence_requests,
            preflight=preflight,
            clarification_required=clarification_required,
            clarification_questions=clarification_questions,
            evidence_status=evidence_status,
            admin_request=admin_request,
        )

    def _preflight(
        self, *, player_message: str, campaign_mode: bool, turn_active: bool
    ) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        git_state = self._git_state()

        message_kind = self._message_kind(player_message)
        # Admin requests are allowed while roleplay is active and do not need
        # campaign mode. They remain read-only until a separate approval step.
        if not campaign_mode and message_kind == "normal_action":
            errors.append("campaign_mode_disabled")
        if turn_active and message_kind == "normal_action":
            errors.append("another_turn_is_active")
        if not player_message.strip():
            errors.append("empty_message")
        if self.require_git and git_state != "clean" and message_kind == "normal_action":
            errors.append(f"git_{git_state}")
        elif git_state != "clean":
            warnings.append(f"git_{git_state}")

        return {
            "campaign_mode": campaign_mode,
            "message_kind": message_kind,
            "working_tree": git_state,
            "turn_active": turn_active,
            "input_enclosed": self._is_enclosed_request(player_message),
            "errors": errors,
            "warnings": warnings,
        }

    def _git_state(self) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo_root), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return "unavailable"

        if result.returncode != 0:
            return "not_a_repository"
        return "dirty" if result.stdout.strip() else "clean"

    @staticmethod
    def _process_type(
        message: str, preflight: dict[str, Any], tags: list[TagEvidence]
    ) -> str:
        """Identify the interaction process before selecting leaf specialists."""
        if preflight.get("message_kind") != "normal_action":
            return str(preflight.get("message_kind") or "command")
        text = message.casefold()
        discussion_markers = (
            "talk to", "speak to", "speak with", "tell ", "ask ",
            "say ", "says ", "discuss", "conversation", "explain to",
            "argue", "debate", "negotiate", "persuade", "reassure",
            "warn ", "reply", "respond", "question ", "listen to",
        )
        quoted_dialogue = ('"' in message or "'" in message) and any(
            marker in text for marker in ("say", "tell", "ask", "reply", "answer")
        )
        if any(marker in text for marker in discussion_markers) or quoted_dialogue:
            return "in_world_discussion"
        return "action"

    @staticmethod
    def _discussion_specialists(
        message: str,
        tag_names: set[str],
        active_npcs: Iterable[str],
        routed: set[str],
    ) -> set[str]:
        """Choose discussion leaf roles without activating generic categories."""
        text = message.casefold()
        specialists = {
            "current_state",
        }
        social = bool(
            {"context.emotional", "participant.companion"} & tag_names
            or any(word in text for word in ("trust", "relationship", "consent", "love", "friend", "argument"))
        )
        if social:
            specialists.add("relationship")
        if active_npcs or any(word in text for word in ("npc", "companion", "dara", "ava", "assistant")):
            specialists.add("npc_autonomy")
        if any(word in text for word in ("link", "telepathy", "relay", "cognitive")):
            specialists.add("cognitive_assistance")
        if any(word in text for word in ("remember", "know", "lore", "what happened", "explain the world")):
            specialists.add("canon")
        # Keep only concrete unlocked branch routes; discard category names
        # such as rules, character, and special from taxonomy output.
        specialists.update(
            name for name in routed
            if name not in {"cache", "rules", "character", "special", "create"}
        )
        return specialists

    @staticmethod
    def _message_kind(message: str) -> str:
        text = message.strip()
        if text.startswith("/"):
            return "command"
        if re.match(r"^(checkpoint|retcon)\b", text, flags=re.IGNORECASE):
            return text.split(maxsplit=1)[0].lower()
        if text.startswith("{") and text.endswith("}"):
            return "out_of_game"
        return "normal_action"

    @classmethod
    def _request_type(cls, message: str, preflight: dict[str, Any]) -> str:
        kind = preflight["message_kind"]
        if kind == "out_of_game":
            return "admin"
        if kind == "command":
            return "command"
        if kind in {"checkpoint", "retcon"}:
            return kind
        if preflight["errors"]:
            return "blocked"
        return "in_game"

    @staticmethod
    def _admin_request(message: str) -> dict[str, Any]:
        """Create a deterministic admin envelope before any model call."""
        text = message.strip()
        if text.startswith("{") and text.endswith("}"):
            text = text[1:-1].strip()
        lowered = text.casefold()
        if re.search(r"\b(instruct|tell|modify|change)\b.*\b(brain|backend|code|specialist)\b", lowered):
            operation = "instruction"
        elif re.search(r"\b(create|make|add|new)\b", lowered):
            operation = "create"
        elif re.search(r"\b(delete|remove|erase)\b", lowered):
            operation = "delete"
        elif re.search(r"\b(update|change|correct|fix|edit|fill)\b", lowered):
            operation = "update"
        elif re.search(r"\b(query|show|list|find|what|why|how|check|investigate)\b", lowered):
            operation = "query"
        else:
            operation = "question"
        if re.search(r"\b(character|npc|relationship|status|modifier|autonomy)\b", lowered):
            target = "character"
        elif re.search(r"\b(brain|backend|code|specialist|router)\b", lowered):
            target = "backend"
        elif re.search(r"\b(rule|document|file|markdown|sheet|ledger)\b", lowered):
            target = "document"
        elif re.search(r"\b(turn|result|resource|history|event)\b", lowered):
            target = "turn_history"
        else:
            target = "game_state"
        ignored_names = {"Why", "What", "When", "Where", "How", "Please", "Show", "Check", "Tell", "Create", "Update"}
        names = [
            name for name in re.findall(r"\b[A-Z][a-zA-Z0-9_-]{2,}\b", text)
            if name not in ignored_names
        ]
        return {
            "operation": operation,
            "target": target,
            "entities": list(dict.fromkeys(names)),
            "write_requested": operation in {"create", "update", "delete", "instruction"},
            "player_message": text,
        }

    @staticmethod
    def _is_enclosed_request(message: str) -> bool:
        text = message.strip()
        return text.startswith("{") and text.endswith("}")

    @staticmethod
    def _new_turn_id(phase: str | None) -> str:
        phase_name = re.sub(r"[^a-z0-9]+", "-", (phase or "unknown").lower()).strip("-")
        return f"turn-{phase_name or 'unknown'}-{uuid.uuid4().hex[:8]}"

    def _classify_message(
        self,
        message: str,
        *,
        classifier: str,
        current_phase: str | None,
        current_state: dict[str, Any],
        active_npcs: Iterable[str],
        temporary_memory: Iterable[str],
    ) -> tuple[list[TagEvidence], str, list[ActionSegment] | None, str, list[str]]:
        if classifier not in {"auto", "heuristic", "deepseek"}:
            raise ValueError("classifier must be auto, heuristic, or deepseek")

        heuristic_tags, heuristic_mode = self._classify_heuristic(message)

        if classifier in {"auto", "deepseek"}:
            api_key = self._deepseek_api_key()
            if api_key:
                model_tags, model_mode, model_segments, _, model_questions = (
                    self._classify_with_deepseek(
                        message,
                        api_key=api_key,
                        current_phase=current_phase,
                        current_state=current_state,
                        active_npcs=active_npcs,
                        temporary_memory=temporary_memory,
                    )
                )
                tags, mode = self._merge_classifications(
                    message,
                    heuristic_tags,
                    heuristic_mode,
                    model_tags,
                    model_mode,
                )
                return tags, mode, model_segments, "hybrid(deepseek+heuristic)", model_questions
            if classifier == "deepseek":
                raise RuntimeError(
                    "DeepSeek classifier requested, but no API key was found. "
                    "Set DEEPSEEK_API_KEY or API_KEY in the existing .env file."
                )

        return heuristic_tags, heuristic_mode, None, "heuristic", []

    @staticmethod
    def _merge_classifications(
        message: str,
        heuristic_tags: list[TagEvidence],
        heuristic_mode: str,
        model_tags: list[TagEvidence],
        model_mode: str,
    ) -> tuple[list[TagEvidence], str]:
        """Merge semantic model output with deterministic guardrails.

        DeepSeek supplies semantic tags.  Heuristics supply hard lexical
        constraints that the model must not override, such as an explicit
        combat/exploration combination or an out-of-band resource/time signal.
        """
        text = message.lower()
        hard_combat = bool(re.search(r"\b(attack|attacks|attacked|fight|fights|fought|strike|strikes|combat|duel)\b", text))
        hard_exploration = bool(re.search(r"\b(explore|enters?|search(?:es|ed)?|investigate|ruin|unmapped)\b", text))
        hard_resource = bool(re.search(r"\b(using|use|spend|spends|consume|consumes|cost|mana|mp|material|ingot|crystal)\b", text))
        hard_time = bool(re.search(r"\b(wait|phase|day|takes? time|until evening|overnight)\b", text))

        if hard_combat and hard_exploration:
            mode = "mixed"
        elif hard_combat:
            mode = "combat"
        elif model_mode in ALLOWED_MODES:
            mode = model_mode
        else:
            mode = heuristic_mode

        merged: dict[str, TagEvidence] = {}
        for item in model_tags:
            if item.tag in ALLOWED_TAGS and not item.tag.startswith("mode."):
                merged[item.tag] = item

        # These are deterministic guardrails, not suggestions from the model.
        hard_tags = {
            "activity.combat": hard_combat,
            "activity.exploration": hard_exploration,
            "mechanic.resource_cost": hard_resource,
            "mechanic.time_cost": hard_time,
        }
        heuristic_by_tag = {item.tag: item for item in heuristic_tags}
        for tag, active in hard_tags.items():
            if active:
                merged[tag] = heuristic_by_tag.get(
                    tag,
                    TagEvidence(tag, "heuristic_guard", f"hard signal detected for {tag}"),
                )

        result = [
            TagEvidence(
                f"mode.{mode}",
                "hybrid_guard",
                f"final mode normalized as {mode}",
            )
        ]
        result.extend(merged.values())
        return result, mode

    @staticmethod
    def _deepseek_api_key() -> str | None:
        # Loading .env changes only this process's environment.  The file is
        # never written, printed, or included in a prompt.
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        return os.getenv("API_KEY")

    def _classify_with_deepseek(
        self,
        message: str,
        *,
        api_key: str,
        current_phase: str | None,
        current_state: dict[str, Any],
        active_npcs: Iterable[str],
        temporary_memory: Iterable[str],
    ) -> tuple[list[TagEvidence], str, list[ActionSegment], str, list[str]]:
        payload = {
            "player_message": message,
            "current_phase": current_phase,
            "current_state": current_state,
            "active_npcs": list(active_npcs),
            "temporary_memory": list(temporary_memory),
        }
        content = ModelGateway(self.repo_root).complete(
            stage="router.classification",
            request_id=None,
            model="deepseek-chat",
            json_mode=True,
            messages=[
                {
                    "role": "system",
                    "content": DEEPSEEK_ROUTER_PROMPT.format(
                        allowed_tags=_taxonomy_prompt_text()
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        ).content
        if not content:
            raise RuntimeError("DeepSeek returned an empty routing response")
        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("DeepSeek returned invalid routing JSON") from exc
        return self._normalize_deepseek_result(result, message)

    @staticmethod
    def _normalize_deepseek_result(
        result: dict[str, Any], message: str
    ) -> tuple[list[TagEvidence], str, list[ActionSegment], str, list[str]]:
        mode = result.get("mode")
        if mode not in ALLOWED_MODES:
            raise RuntimeError(f"DeepSeek returned invalid mode: {mode!r}")

        raw_tags = result.get("tags")
        if not isinstance(raw_tags, list):
            raise RuntimeError("DeepSeek routing response is missing a tags list")

        tags: list[TagEvidence] = [
            TagEvidence(
                tag=f"mode.{mode}",
                source="deepseek",
                evidence=f"DeepSeek classified mode as {mode}",
            )
        ]
        seen = {tags[0].tag}
        for item in raw_tags:
            if not isinstance(item, dict):
                raise RuntimeError("DeepSeek returned a malformed tag")
            tag = item.get("tag")
            evidence = item.get("evidence")
            if tag not in ALLOWED_TAGS:
                # The model is semantic, but the taxonomy identifiers are
                # canonical. Ignore an unsupported model label and retain the
                # deterministic/heuristic classification instead of crashing.
                continue
            if not isinstance(evidence, str) or not evidence.strip():
                continue
            if tag not in seen:
                tags.append(TagEvidence(tag, "deepseek", evidence.strip()))
                seen.add(tag)

        raw_segments = result.get("segments")
        if not isinstance(raw_segments, list) or not raw_segments:
            raw_segments = [{"text": message, "classification": mode, "tags": []}]

        segments: list[ActionSegment] = []
        all_tag_names = [item.tag for item in tags]
        for index, item in enumerate(raw_segments, start=1):
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                raise RuntimeError("DeepSeek returned a malformed action segment")
            segment_tags = item.get("tags", [])
            if not isinstance(segment_tags, list):
                segment_tags = []
            # Keep only canonical tags selected in the top-level response.
            # Unknown segment labels are model-output noise, not a pipeline
            # failure; an unlabelled segment inherits the selected tags.
            segment_tags = [tag for tag in segment_tags if tag in all_tag_names]
            segments.append(
                ActionSegment(
                    segment_id=index,
                    text=item["text"].strip(),
                    tags=segment_tags or all_tag_names,
                    classification=str(item.get("classification", mode)),
                )
            )

        questions = result.get("clarification_questions", [])
        if not isinstance(questions, list) or any(not isinstance(q, str) for q in questions):
            raise RuntimeError("DeepSeek returned malformed clarification questions")
        clarification_required = result.get("clarification_required", False)
        if not isinstance(clarification_required, bool):
            raise RuntimeError("DeepSeek returned malformed clarification status")
        return tags, mode, segments, "deepseek", questions if clarification_required else []

    def _unlocked_branch_tags(self, message: str) -> list[TagEvidence]:
        text = message.casefold()
        result: list[TagEvidence] = []
        for branch, entry in self.branch_registry.entries().items():
            if str(entry.get("status", "locked")).casefold() != "unlocked":
                continue
            tags = entry.get("activation_tags", [])
            if isinstance(tags, str):
                tags = [tags]
            for tag in tags:
                tag_text = str(tag)
                keyword = tag_text.rsplit(".", 1)[-1].replace("_", " ").casefold()
                stem = keyword[:-3] if keyword.endswith("ing") else keyword
                if keyword and (keyword in text or (stem and stem in text)):
                    result.append(TagEvidence(tag_text, "branch_registry", f"unlocked branch {branch}: {keyword}"))
        return result

    def _classify_heuristic(self, message: str) -> tuple[list[TagEvidence], str]:
        text = message.lower()
        tags: list[TagEvidence] = []

        def add(tag: str, *terms: str) -> None:
            def present(term: str) -> bool:
                needle = term.lower()
                if len(needle) <= 3:
                    return bool(re.search(rf"\b{re.escape(needle)}\b", text))
                return needle in text

            matched = next((term for term in terms if present(term)), None)
            if matched:
                tags.append(TagEvidence(tag, "player_input", matched))

        # A weapon or enemy mention alone is not combat.  Require an
        # explicit hostile action so that "train with a sword" stays noncombat.
        combat = bool(re.search(
            r"\b(attack|attacks|attacked|fight|fights|fought|strike|strikes|combat|duel)\b",
            text,
        ))
        exploration = bool(re.search(
            r"\b(explore|enters?|search(?:es|ed)?|investigate|ruin|unmapped)\b",
            text,
        ))

        if combat:
            tags.extend([
                TagEvidence("activity.combat", "player_input", "combat action"),
                TagEvidence("mechanic.position", "player_input", "combat positioning may matter"),
                TagEvidence("stakes.life_threatening", "player_input", "hostile encounter"),
            ])
            mode = "mixed" if exploration else "combat"
        else:
            mode = "noncombat"

        # The taxonomy is also the heuristic vocabulary.  This keeps offline
        # behavior and the DeepSeek prompt aligned with the same definitions.
        for tag, definition in TAG_DEFINITIONS.items():
            if definition.get("category") != "mode":
                add(tag, *definition.get("positive_indicators", []))

        if any(word in text for word in ("irreversible", "permanent", "change her", "dangerous")):
            tags.append(TagEvidence("stakes.irreversible", "player_input", "potentially irreversible action"))
        elif combat:
            tags.append(TagEvidence("stakes.contested", "player_input", "opposed action"))
        else:
            tags.append(TagEvidence("stakes.low", "player_input", "no high-risk marker detected"))

        tags.insert(
            0,
            TagEvidence(
                f"mode.{mode}",
                "heuristic",
                f"mode inferred as {mode}",
            ),
        )

        # Preserve first evidence item for each tag.
        unique: dict[str, TagEvidence] = {}
        for item in tags:
            unique.setdefault(item.tag, item)
        return list(unique.values()), mode

    @staticmethod
    def _segment_actions(
        message: str, tags: list[TagEvidence], mode: str
    ) -> list[ActionSegment]:
        text = message.strip().strip("{} ")
        pieces = [p.strip() for p in re.split(r"\s*(?:,|;|\band then\b|\bthen\b)\s*", text, flags=re.IGNORECASE) if p.strip()]
        if not pieces:
            pieces = [text]

        tag_names = [item.tag for item in tags]
        segments: list[ActionSegment] = []
        for index, piece in enumerate(pieces, start=1):
            segment_tags = tag_names if len(pieces) == 1 else TurnRouter._tags_for_segment(piece, tag_names)
            classification = "combat" if "activity.combat" in segment_tags else "noncombat"
            segments.append(ActionSegment(index, piece, segment_tags, classification))
        return segments

    @staticmethod
    def _tags_for_segment(text: str, tags: list[str]) -> list[str]:
        lowered = text.lower()
        if any(word in lowered for word in ("attack", "fight", "strike", "enemy", "creature")):
            return [tag for tag in tags if tag.startswith("mode.") or tag.startswith("activity.combat") or tag.startswith("participant.enemy") or tag.startswith("stakes.") or tag.startswith("mechanic.")]
        if any(word in lowered for word in ("search", "explore", "study", "investigate", "enter")):
            return [tag for tag in tags if "exploration" in tag or "research" in tag or "unknown_area" in tag or "world" in tag]
        return tags

    @staticmethod
    def _build_evidence_requests(tags: list[TagEvidence]) -> list[dict[str, Any]]:
        requests: list[dict[str, Any]] = []
        for item in tags:
            request = EVIDENCE_REQUESTS.get(item.tag)
            if request:
                requests.append({"tag": item.tag, **request})
        return requests

    @staticmethod
    def _clarification_questions(
        tags: list[TagEvidence], mode: str, segments: list[ActionSegment]
    ) -> list[str]:
        questions: list[str] = []
        tag_names = {item.tag for item in tags}
        if mode == "mixed" and len(segments) == 1:
            questions.append("Does this contain one continuous action or separate exploration and combat actions?")
        if {"stakes.low", "stakes.life_threatening"}.issubset(tag_names):
            questions.append("The action has conflicting risk signals. Which risk level should apply?")
        return questions


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a campaign turn routing record.")
    parser.add_argument("message", help="The player's message")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--phase", default=None)
    parser.add_argument("--campaign-mode", action="store_true")
    parser.add_argument("--turn-active", action="store_true")
    parser.add_argument("--allow-no-git", action="store_true")
    parser.add_argument(
        "--classifier",
        choices=("auto", "heuristic", "deepseek"),
        default="auto",
        help="Use DeepSeek when configured, or choose a classifier explicitly.",
    )
    args = parser.parse_args()

    router = TurnRouter(args.repo_root, require_git=not args.allow_no_git)
    record = router.route(
        args.message,
        campaign_mode=args.campaign_mode,
        current_phase=args.phase,
        turn_active=args.turn_active,
        classifier=args.classifier,
    )
    print(json.dumps(record.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
