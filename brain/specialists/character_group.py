"""Character-specific specialist construction.

Each important character receives independent, domain-bounded specialists.  The
specialists share an evidence anchor but do not share ownership of the
character's whole mind or history.
"""
from __future__ import annotations

import re
from typing import Any

from brain.specialists.registry import SpecialistDefinition, register_specialist


CHARACTER_SPECIALIST_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "key": "identity_behavior",
        "label": "Identity and Behavioral State",
        "sections": ("Voice and Reactions", "Motives and Status"),
        "specialists": ("current_state",),
        "questions": (
            "How does this character's description shape voice, reactions, motives, and current status?",
            "What behavior is established, uncertain, or changing?",
        ),
        "evidence_requirements": ("character description", "character history", "current status records"),
        "style": "Behaviorally observant, psychologically consistent, and cautious about unknown motives.",
        "scope": "voice, reactions, motives, habits, current status, and behavior changes",
        "task_prompt": "Own this character's identity, voice, reactions, motives, and current behavioral state. Do not infer hidden motives or answer for other characters.",
    },
    {
        "key": "stats",
        "label": "Stats and Stat Modifiers",
        "sections": ("Core Stats", "Derived Stats", "Stat Modifiers"),
        "specialists": ("modifier", "create_stat_modifier"),
        "questions": (
            "What are this character's core and derived stats?",
            "Which broad stat-specific modifiers, capacities, and unlocks apply?",
        ),
        "evidence_requirements": ("approved core stats", "derived-stat rules", "stat modifier records"),
        "style": "Mechanically precise, evidence-bound, and explicit about capability limits.",
        "scope": "core stats, derived values, broad Stat Modifiers, and mechanical capability limits",
        "task_prompt": "Own this character's stats, derived values, and broad Stat Modifier domains. Stat Modifiers must remain broad across multiple relevant situations; narrow techniques belong to Effect Modifiers.",
    },
    {
        "key": "actions_effects",
        "label": "Actions and Effect Modifiers",
        "sections": ("Actions", "Effect Modifiers"),
        "specialists": ("modifier", "create_effect_modifier", "experimentation"),
        "questions": (
            "What action patterns and techniques does this character demonstrate?",
            "Which reusable Effect Modifiers, conditions, limits, and upgrades apply?",
        ),
        "evidence_requirements": ("action history", "effect modifier records", "experimentation or training evidence"),
        "style": "Concrete and action-focused; separates demonstrated techniques from general stats.",
        "scope": "action patterns, techniques, Effect Modifiers, activation, limits, and growth",
        "task_prompt": "Own this character's demonstrated action patterns, techniques, Effect Modifiers, activation conditions, limitations, experimentation, and growth. Keep techniques separate from broad Stat Modifiers.",
    },
    {
        "key": "class",
        "label": "Class and Class Modifiers",
        "sections": ("Class", "Class Modifiers"),
        "specialists": ("class",),
        "questions": (
            "What class identity, progression, and class rules apply?",
            "Which class-specific modifiers and class slots are available?",
        ),
        "evidence_requirements": ("approved class", "class rules", "class modifier records"),
        "style": "Progression-aware and rule-bound; never turns a profession into an acquired class.",
        "scope": "class identity, progression, class slots, and class-specific capabilities",
        "task_prompt": "Own this character's acquired class, class progression, class slots, and Class Modifiers. Never convert a profession or background into a class.",
    },
    {
        "key": "active_skills_spells",
        "label": "Active Skills and Spells",
        "sections": ("Active Skills", "Spells"),
        "specialists": ("active_skills_spells", "class"),
        "questions": (
            "Which active skills and spells are established for this character?",
            "What activation conditions, costs, limits, and progression rules apply?",
        ),
        "evidence_requirements": ("active skill records", "spell records", "class and progression records"),
        "style": "Mechanically precise and evidence-bound; never invents an unlocked skill or spell.",
        "scope": "active system skills, spells, activation, costs, limits, and progression",
        "task_prompt": "Own this character's established active system skills and spells. Keep them distinct from Effect Modifiers, require evidence for unlocks, and preserve activation conditions, costs, limitations, and progression rules.",
    },
    {
        "key": "social_autonomy",
        "label": "Social and Autonomy",
        "sections": ("Relationships", "Participation and Consent", "Autonomy"),
        "specialists": ("relationship", "npc_autonomy"),
        "questions": (
            "Which relationships and relationship changes apply?",
            "What participation, consent, autonomy, and independent behavior rules apply?",
        ),
        "evidence_requirements": ("relationship records", "participation and consent records", "autonomy records"),
        "style": "Socially attentive and autonomy-preserving; disagreement and refusal remain valid outcomes.",
        "scope": "relationships, participation, consent, boundaries, disagreement, and autonomy",
        "task_prompt": "Own this character's relationships, participation, consent, boundaries, disagreement, refusal, and autonomy. Never assume cooperation or consent from party membership.",
    },
)

_GROUPS_BY_ROLE: dict[str, tuple[str, ...]] = {
    # Player and core party characters are central to the game and receive the
    # full five-lens character model.
    "player": ("stats", "actions_effects", "class", "active_skills_spells"),
    "party": tuple(item["key"] for item in CHARACTER_SPECIALIST_GROUPS),
    # Non-party characters receive durable specialists for identity, actions,
    # and social behavior. Stats and class are added only when their evidence
    # or narrative importance promotes them to a core/party character.
    "non_party": ("identity_behavior", "actions_effects", "social_autonomy"),
}


def _slug(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "character").casefold()).strip("_")
    return text or "character"


def _normalize_role(role: object) -> str:
    value = str(role or "party").casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "main": "player",
        "main_character": "player",
        "player_character": "player",
        "party_member": "party",
        "npc": "non_party",
        "nonparty": "non_party",
        "non_party_character": "non_party",
    }
    return aliases.get(value, value if value in _GROUPS_BY_ROLE else "party")


def _register_character_specialist(proposal: dict[str, Any]) -> SpecialistDefinition:
    definition = SpecialistDefinition(
        name=str(proposal["name"]),
        purpose=str(proposal["purpose"]),
        questions=tuple(str(item) for item in proposal.get("questions", [])),
        activation_tags=tuple(str(item) for item in proposal.get("activation_tags", [])),
        category="character",
        unlockable=False,
        description=str(proposal.get("prompt") or proposal["purpose"]),
        sections=tuple(str(item) for item in proposal.get("sections", [])),
        evidence_requirements=tuple(str(item) for item in proposal.get("evidence_requirements", [])),
        task_prompt=str(proposal.get("task_prompt") or "Own only this character-scoped domain."),
    )
    return register_specialist(definition)


def register_character_specialists(groups: object) -> list[SpecialistDefinition]:
    """Rehydrate character-scoped definitions into the runtime registry."""
    values = groups.values() if isinstance(groups, dict) else groups if isinstance(groups, list) else []
    registered: list[SpecialistDefinition] = []
    for group in values:
        entries = group if isinstance(group, list) else [group]
        for proposal in entries:
            if isinstance(proposal, dict) and proposal.get("name"):
                registered.append(_register_character_specialist(proposal))
    return registered


def character_specialist_group(
    character: dict[str, Any],
    *,
    role: str = "party",
    assumption_authorized: bool = False,
) -> list[dict[str, Any]]:
    """Build unique, domain-bounded specialists for one character.

    ``role`` controls the durable specialist count. Player and core party
    characters receive all five lenses; non-party characters receive the three
    lenses needed for identity, action, and social continuity. The role is a
    routing/coverage decision, not evidence about the character's personality.
    """
    identity = character.get("identity") if isinstance(character.get("identity"), dict) else {}
    name = str(identity.get("name") or character.get("name") or "Character")
    slug = _slug(name)
    character_role = _normalize_role(role or character.get("role"))
    description = str(character.get("description") or "").strip()
    description_note = description or "No description supplied; keep claims provisional and evidence-seeking."
    agency = (
        "This is the player-controlled character. Never decide the player's action, belief, or consent; return options and consequences for the player to choose."
        if character_role == "player"
        else "This character has independent agency. Preserve the right to disagree, refuse, reinterpret events, or act according to established motives and boundaries."
    )
    party_boundary = (
        "This character is a core party member; participation is not automatic and cooperation still requires relevant consent or established circumstances."
        if character_role == "party"
        else "This character is not a core party member; do not assume availability, loyalty, knowledge, or cooperation without evidence."
    )
    allowed = set(_GROUPS_BY_ROLE[character_role])
    proposals: list[dict[str, Any]] = []
    for group in CHARACTER_SPECIALIST_GROUPS:
        key = str(group["key"])
        if key not in allowed:
            continue
        proposal = {
            "name": f"character_{slug}_{key}",
            "character_name": name,
            "character_slug": slug,
            "character_role": character_role,
            "group_key": key,
            "label": group["label"],
            "purpose": (
                f"Own {name}'s {group['label'].casefold()} as a dedicated character-scoped specialist. "
                f"Do not answer for other characters or domains."
            ),
            "prompt": (
                f"You are the dedicated {group['label'].casefold()} specialist for {name}. "
                f"Your owned scope is {group['scope']}. {agency} {party_boundary} "
                f"Character evidence anchor: {description_note} "
                f"Working style: {group['style']} "
                "Use only approved character evidence, scoped history, and applicable rules. "
                "Do not convert missing facts into established history, and do not let another character's record fill a gap."
            ),
            "style": group["style"],
            "scope": group["scope"],
            "task_prompt": group["task_prompt"],
            "questions": list(group["questions"]),
            "activation_tags": [f"character.{slug}", f"character_group.{key}"],
            "category": "character",
            "unlockable": False,
            "sections": list(group["sections"]),
            "base_specialists": list(group["specialists"]),
            "evidence_requirements": list(group["evidence_requirements"]),
            "status": "proposed",
        }
        registered = _register_character_specialist(proposal)
        proposal["registry_name"] = registered.name
        proposal["specialists"] = [registered.name]
        if assumption_authorized:
            proposal["initialization_assumption"] = {
                "status": "provisional",
                "player_authorized": True,
                "scope": "current_entity",
                "statement": (
                    f"For {name}'s {group['label'].casefold()} specialist, use the supplied "
                    "description and approved records as the initial evidence boundary; "
                    "do not treat missing facts as established history."
                ),
                "limitations": [
                    "This initializes specialist requirements only.",
                    "It does not grant modifiers, class abilities, relationships, or autonomy facts.",
                    "Missing facts remain evidence requests for later play.",
                ],
                "persistence": "temporary_memory",
            }
        proposals.append(proposal)
    return proposals
