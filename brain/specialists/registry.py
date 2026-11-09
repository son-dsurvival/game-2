"""Specialist contracts for evidence-backed turn analysis."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re


@dataclass(frozen=True)
class SpecialistDefinition:
    """A bounded specialist role.

    ``category`` is the orchestration lane, not a second permission system:
    core roles always run, while ``special`` roles are unlocked by a campaign
    branch.  Keeping this metadata beside the prompt makes the registry the
    single source of truth for routing, evidence scoping, and creation.
    """

    name: str
    purpose: str
    questions: tuple[str, ...]
    activation_tags: tuple[str, ...] = ()
    mandatory: bool = False
    category: str = "special"
    unlockable: bool = False
    description: str = ""
    template: str | None = None
    sections: tuple[str, ...] = ()
    evidence_requirements: tuple[str, ...] = ()


# Core specialists are analysis categories. Evidence Bundle construction and
# Recorder persistence handle context and memory; there is no mandatory cache
# specialist. Special is a category that monitors relevant unlocked branches.
CORE_SPECIALISTS = ("rules", "character", "special")


def _core(
    name: str,
    purpose: str,
    questions: tuple[str, ...],
    *,
    activation_tags: tuple[str, ...] = (),
) -> SpecialistDefinition:
    return SpecialistDefinition(
        name=name,
        purpose=purpose,
        questions=questions,
        activation_tags=activation_tags,
        mandatory=True,
        category="core",
        description=purpose,
    )


def _routed(
    name: str,
    purpose: str,
    questions: tuple[str, ...],
    *,
    activation_tags: tuple[str, ...] = (),
) -> SpecialistDefinition:
    return SpecialistDefinition(
        name=name,
        purpose=purpose,
        questions=questions,
        activation_tags=activation_tags,
        mandatory=False,
        category="special",
        description=purpose,
    )


SPECIALIST_DEFINITIONS: dict[str, SpecialistDefinition] = {
    # The three core analysis categories run on every normal turn. Evidence
    # Bundle construction supplies scoped context; Create remains explicitly
    # routed when a recurring uncovered domain is detected.
    "cache": _core(
        "cache",
        (
            "Review the new conversation against the previous game cache and "
            "the supplied evidence. Extract only durable context needed by the "
            "runtime: active intentions, unresolved threads, commitments, NPC "
            "plans, pending event conditions, discoveries, and facts that may "
            "expire. This is a memory preprocessor, not a resolver. It never "
            "creates canon, resolves outcomes, or overwrites established facts."
        ),
        (
            "What durable facts or commitments were added, confirmed, superseded, or expired?",
            "Which unresolved threads, questions, and pending conditions must remain available?",
            "Which facts are temporary, uncertain, or tied to a specific source turn?",
        ),
        activation_tags=("context.history", "context.memory", "context.conversation"),
    ),
    "rules": _core(
        "rules",
        (
            "Own every game rule and mechanical question: combat and noncombat "
            "procedures, difficulty, XP, time, resources, experiments, validity, "
            "costs, and resolution boundaries. This specialist explains which "
            "rules apply and which are excluded; it does not resolve the final "
            "outcome or roll dice."
        ),
        (
            "Which combat or noncombat rules apply, and which are excluded?",
            "What difficulty, XP, time, resource, experiment, and validity rules govern this action?",
            "What exact mechanical inputs and unresolved rule conflicts must the Lead Resolver use?",
        ),
        activation_tags=("mode.combat", "mechanic.difficulty", "mechanic.resource_cost", "mechanic.time_cost", "activity.experiment"),
    ),
    "character": _core(
        "character",
        (
            "Monitor the player character and every named character: status, health, "
            "relationships, modifiers, autonomy, motives, participation, consent, "
            "resources held by the character, and any other character-specific state."
        ),
        (
            "What current status and character facts apply to each named person?",
            "What relationship, modifier, autonomy, motive, and participation effects apply?",
            "Which character facts are stale, contradictory, or missing?",
        ),
        activation_tags=("participant.companion", "context.emotional", "mechanic.cognitive_assistance"),
    ),
    "special": _routed(
        "special",
        (
            "Monitor only branches marked unlocked in the Branch Registry. Use "
            "this lane for unique lore or player-created domains such as business, alchemy, "
            "class, politics, relay systems, factions, or other branches that "
            "have expanded enough to require dedicated monitoring. Do not invent "
            "a specialist when no branch evidence supports one."
        ),
        (
            "Which unlocked special branches are relevant to this action?",
            "What lore-specific rules, state, and consequences does each branch require?",
            "Does an expanding branch need a new specialist proposal?",
        ),
        activation_tags=("activity.business", "context.class_system", "context.factional", "context.relay_system"),
    ),
    "create": _routed(
        "create",
        (
            "Read the complete rules, current state, character records, world lore, "
            "and active branch evidence. When a branch becomes active or a new "
            "player character arrives, audit whether the existing Rules, Character, "
            "and Special categories cover the new recurring domain. Propose a new "
            "bounded specialist only when a genuinely uncovered recurring domain "
            "exists, and verify that existing scopes remain current. This role "
            "proposes definitions; it never silently changes canon or executes "
            "a proposal. A new character normally receives a unique Character "
            "specialist context, not an unnecessary new global specialist."
        ),
        (
            "When a branch is unlocked or a new player character arrives, is an existing category or leaf specialist insufficient?",
            "Does the new domain need a unique Character specialist context, a Special branch specialist, or only existing coverage?",
            "What new specialist name, purpose, questions, and activation tags would safely cover a genuinely recurring gap?",
            "Which existing specialist scopes need an update or are already sufficient?",
        ),
    ),
    "canon": SpecialistDefinition(
        "canon",
        "Check established lore, character facts, and canon conflicts.",
        ("What established facts apply?", "Are any canon claims in conflict?", "What facts are unknown?"),
        category="character",
    ),
    "current_state": SpecialistDefinition(
        "current_state",
        "Check the current day, phase, location, conditions, and active state.",
        ("What current state facts apply?", "Is any state stale or missing?", "What state must be confirmed?"),
        category="character",
    ),    "difficulty": SpecialistDefinition(
        "difficulty",
        "Calculate the task-side target only: the numeric Task Value or opponent Reaction Total without rolling or resolving success. Derive the experiment tier, Difficulty, Novelty, applicable task factors, actual risk, Independence, and Practice Carryover reduction from the player's plausible declared action and the rules. Do not calculate Action Value, stats, skills, tools, or d20.",
        ("Is this resolved against a Task Value or an opponent Reaction Total?", "What tier and procedure are reasonably established by the player's declared action?", "What exact numeric Difficulty, Novelty, Integration, Independence, Field-Risk, Practice Carryover, and target formula should the Lead Resolver use?"),
        ("mechanic.difficulty", "mechanic.dice", "mode.combat", "activity.experiment", "mechanic.spell_creation"),
    ),
    "combat": SpecialistDefinition(
        "combat",
        "Analyze combat threats, positioning, defenses, attacks, and combat constraints without rolling.",
        ("What combat rules and positions matter?", "What risks and defenses are relevant?", "What must be resolved later?"),
        ("mode.combat",),
    ),
    "experimentation": SpecialistDefinition(
        "experimentation",
        "Analyze whether an action is an experiment and whether prior practice transfers.",
        ("Is this a valid experiment?", "Does comparable prior practice exist?", "Do Practice Carryover or Lineage Familiarity apply?"),
        ("activity.experiment",),
    ),
    "relationship": SpecialistDefinition(
        "relationship",
        "Analyze emotional context, bonds, trust, consent, boundaries, and relationship effects.",
        ("What relationship facts apply?", "What emotional or consent boundaries matter?", "What relationship changes are possible?"),
        ("context.emotional", "context.relationship", "mechanic.relationship_change"),
    ),
    "npc_autonomy": SpecialistDefinition(
        "npc_autonomy",
        "Analyze an NPC's independent motives, approval, compliance, resistance, and possible initiative.",
        ("What does the NPC want?", "Will they approve or comply?", "Could they warn, resist, refuse, or act independently?"),
        ("participant.companion", "mechanic.npc_autonomy"),
    ),
    "resources": SpecialistDefinition(
        "resources",
        "Analyze required, consumed, available, and efficiency-modified resources.",
        ("What resources are required?", "What is consumed?", "Are sufficient resources evidenced?"),
        ("mechanic.resource_cost",),
    ),
    "modifier": SpecialistDefinition(
        "modifier",
        "Calculate the action-side modifier breakdown only. Determine the correct physical or magical stat basis, Average Relevant Stats, stat/class/skill modifiers, tools, preparation, allies, assistance, environmental Action modifiers, Realistic Approach, Practice Carryover added to Action, resources, materials, time, and cost. For spells, mana actions, and magical shields, inspect the Status Sheet Modifier Index for INT/WIS, mana, spell, concentration, systems, and flow modifiers. Do not calculate the final Task Value or opponent Reaction Total; the difficulty specialist owns that target. Treat plausible player-declared conditions as active unless contradicted.",
        ("Who is the primary actor and who is actively helping?", "Which exact numeric stat, skill, tool, preparation, teamwork, active-node, assistance, Realistic Approach, resource, cost, and timing modifiers apply?", "What are each participant's Action Values, Main/Sub relationship boost, Sub contribution, and final Team Action Value? Which action-side modifiers apply, which are +0, and which are excluded with a reason?"),
        ("mechanic.resource_cost", "mechanic.cognitive_assistance", "mechanic.spell_creation", "mechanic.difficulty", "mode.combat"),
    ),
    "create_stat_modifier": SpecialistDefinition(
        "create_stat_modifier",
        (
            "Design character-specific starting or earned Stat Modifier options from the "
            "character's stated life, demonstrated capability, meaningful practice, and "
            "the supplied evidence. Return exactly five distinct valid choices when a "
            "design is requested, including a no-modifier choice when the evidence does "
            "not justify five positive options. Never grant raw stats, invent history, "
            "or bypass the universal stat-modifier laws. Each option must state the "
            "affected stat, major/minor classification, magnitude, evidence, limits, "
            "growth or conversion rule, and stacking behavior."
        ),
        (
            "Which character evidence supports a Stat Modifier or a no-modifier choice?",
            "Which stat, major/minor classification, magnitude, limits, and growth rule apply?",
            "What five distinct options can the player choose from without inventing history or violating tier rules?",
        ),
        ("mechanic.modifier_creation", "context.class_system", "activity.training", "stakes.breakthrough"),
        category="character",
    ),
    "create_effect_modifier": SpecialistDefinition(
        "create_effect_modifier",
        (
            "Design character-specific starting or earned reusable Effect Modifier options "
            "from the character's stated life, demonstrated capability, meaningful practice, "
            "player-authored design brief, and supplied evidence. Return exactly five "
            "distinct valid choices when a design is requested, including a no-modifier "
            "choice when necessary. A player may request something novel; novelty is not "
            "a violation by itself. Do not grant the modifier or invent history. Every "
            "option must include activation conditions, limitations, anti-farming boundary, "
            "stacking behavior, and evidence-backed Modifier Group placement."
        ),
        (
            "What character history, current design brief, or meaningful achievement supports an Effect Modifier?",
            "Is each effect stable, narrow, reusable, non-duplicative, and compatible with tier and material rules?",
            "What five distinct options, limitations, activation conditions, placements, and upgrade paths can the player choose from?",
        ),
        ("mechanic.modifier_creation", "activity.experiment", "activity.training", "stakes.breakthrough", "mode.combat"),
        category="character",
    ),
    # Compatibility name for saved routes and old records. New setup and
    # routing use the two typed character specialists above.
    "modifier_creation": SpecialistDefinition(
        "modifier_creation",
        "Legacy modifier-design compatibility lane; use create_stat_modifier or create_effect_modifier for new work.",
        ("Which typed modifier designer should handle this request?", "What evidence and rules apply?", "Is a new design justified?"),
        ("mechanic.modifier_creation",),
        category="character",
    ),
    "spell": SpecialistDefinition(
        "spell",
        "Determine spell-specific validity, generation cost, casting cost, tier, branch, and spell-effect constraints.",
        ("Which spell system and branch apply?", "What generation cost follows from the spell's power and effect?", "Which casting costs, tier limits, and stability rules apply?"),
        ("mechanic.spell_creation", "activity.crafting", "activity.experiment", "context.relay_system"),
    ),
    "time": SpecialistDefinition(
        "time",
        "Analyze action duration, phase costs, waiting, urgency, and time availability.",
        ("Is this a major or minor action?", "How much time is required?", "Can it occur in the current phase?"),
        ("mechanic.time_cost",),
    ),
    "world": SpecialistDefinition(
        "world",
        (
            "Run the Dynamic World Event rules at the start of a new game day. "
            "Review the completed day, update the explicit 1–100 Event Trigger "
            "number pool by transferring exact numbers between triggers, validate "
            "that every number has one owner, and use the single d100 result to "
            "design the selected event. Any generated event must include an "
            "encounter condition and the latest phase by which that encounter can "
            "occur. Do not reroll, invent unrecorded pool changes, or resolve the "
            "player's response."
        ),
        (
            "What completed-day development justifies each pool adjustment?",
            "Which exact numbers move from which trigger to which trigger, and do the pools still contain every number from 1–100 exactly once?",
            "What d100 result selected the trigger, and what event tier and circumstances are allowed?",
            "What encounter condition must be true, and what is the latest phase for the encounter?",
        ),
        ("activity.exploration", "context.environmental", "context.unknown_area", "mechanic.world_event"),
    ),
    "xp": SpecialistDefinition(
        "xp",
        "Analyze learning, training, progression, and experience eligibility without awarding XP.",
        ("Can this action produce learning?", "What progression rules apply?", "What evidence would support XP later?"),
        ("mechanic.xp", "activity.training"),
    ),
    "cognitive_assistance": SpecialistDefinition(
        "cognitive_assistance",
        "Analyze whether memory, analysis, advice, databases, or assistance modifiers apply.",
        ("What assistance is requested?", "Are assistance requirements satisfied?", "Which assistance modifiers are valid?"),
        ("mechanic.cognitive_assistance",),
    ),
    "consequences": SpecialistDefinition(
        "consequences",
        "Identify possible irreversible, factional, visibility, relationship, and world consequences without resolving them.",
        ("What could become irreversible?", "Which people, factions, or systems could be affected?", "What consequence evidence is missing?"),
        ("stakes.irreversible", "stakes.contested", "stakes.field_risk"),
    ),
    "class": SpecialistDefinition(
        "class",
        "Analyze the player's class, class skills, class modifiers, and class progression as they relate to the action.",
        ("Which class facts apply?", "Which class abilities or modifiers are valid?", "What class information is missing?"),
        ("context.class_system",),
    ),
    "relay": SpecialistDefinition(
        "relay",
        "Analyze relay architecture, relay state, relay limits, relay resources, and relay-specific mechanics.",
        ("Which relay facts apply?", "What relay constraints or resources matter?", "What relay-specific evidence is missing?"),
        ("context.relay_system", "mechanic.world_event"),
    ),
    "business": SpecialistDefinition(
        "business",
        "Analyze business operations, trade, contracts, markets, finances, and enterprise consequences.",
        ("What business facts apply?", "What trade or financial constraints matter?", "What business consequences or evidence gaps exist?"),
        ("activity.business", "context.factional"),
    ),
    "alchemy": SpecialistDefinition(
        "alchemy",
        "Analyze the campaign's unlocked alchemy branch, including recipes, reagents, procedures, safety, quality, and progression.",
        ("Which alchemy rules and recipes apply?", "Which reagents, risks, time, and resources matter?", "What alchemy branch state or evidence is missing?"),
        ("activity.alchemy", "mechanic.alchemy"),
    ),
    "politics": SpecialistDefinition(
        "politics",
        "Analyze the campaign's unlocked political branch, including factions, offices, influence, negotiations, policy, and political consequences.",
        ("Which factions, offices, and political rules apply?", "What influence, relationship, and negotiation constraints matter?", "What political consequence or evidence gap must be tracked?"),
        ("activity.politics", "context.political", "context.factional"),
    ),
}

# Legacy domain roles remain available as explicit, finer-grained specialists.
# They are not additional always-on lanes; the four core roles above own the
# normal turn.  This preserves existing saved routes while making unlockability
# explicit for new campaigns.
_RULE_DOMAIN_NAMES = {"difficulty", "combat", "experimentation", "resources", "spell", "time", "xp"}
_CHARACTER_DOMAIN_NAMES = {"canon", "current_state", "relationship", "npc_autonomy", "modifier", "cognitive_assistance"}
_UNLOCKABLE_SPECIAL_NAMES = {"world", "consequences", "class", "relay", "business", "alchemy", "politics"}
for _name in _RULE_DOMAIN_NAMES:
    if _name in SPECIALIST_DEFINITIONS:
        SPECIALIST_DEFINITIONS[_name] = replace(SPECIALIST_DEFINITIONS[_name], category="rules")
for _name in _CHARACTER_DOMAIN_NAMES:
    if _name in SPECIALIST_DEFINITIONS:
        SPECIALIST_DEFINITIONS[_name] = replace(SPECIALIST_DEFINITIONS[_name], category="character")
for _name in _UNLOCKABLE_SPECIAL_NAMES:
    if _name in SPECIALIST_DEFINITIONS:
        SPECIALIST_DEFINITIONS[_name] = replace(
            SPECIALIST_DEFINITIONS[_name], category="special", unlockable=True
        )

SPECIALIST_GROWTH_NOTE = (
    "Rules, Character, and Special are the three core analysis categories. "
    "Create audits new player-character arrivals and unlocked branches for "
    "genuinely recurring uncovered domains, proposes bounded definitions, and "
    "checks that existing scopes stay current."
)

_CREATED_NAME = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


def validate_created_definition(value: object) -> SpecialistDefinition | None:
    """Convert a Create Specialist proposal into a safe in-memory definition.

    Proposals are deliberately not written to the repository.  The caller can
    present them for approval or include them in the next routing record.  This
    keeps an LLM from silently changing the campaign backend or executing code.
    """
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    purpose = value.get("purpose")
    questions = value.get("questions", ())
    tags = value.get("activation_tags", ())
    if (
        not isinstance(name, str)
        or not _CREATED_NAME.fullmatch(name)
        or name in SPECIALIST_DEFINITIONS
        or not isinstance(purpose, str)
        or not purpose.strip()
        or not isinstance(questions, list)
        or not questions
        or any(not isinstance(item, str) or not item.strip() for item in questions)
        or not isinstance(tags, list)
        or any(not isinstance(item, str) or not item.strip() for item in tags)
    ):
        return None
    sections_value = value.get("sections", [])
    sections = tuple(str(item).strip() for item in sections_value[:12] if str(item).strip()) if isinstance(sections_value, list) else ()
    evidence_value = value.get("evidence_requirements", [])
    evidence = tuple(str(item).strip() for item in evidence_value[:12] if str(item).strip()) if isinstance(evidence_value, list) else ()
    template = value.get("template")
    if template is not None and (not isinstance(template, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*\.md", template)):
        return None
    return SpecialistDefinition(
        name=name,
        purpose=purpose.strip(),
        questions=tuple(item.strip() for item in questions[:6]),
        activation_tags=tuple(dict.fromkeys(item.strip() for item in tags)),
        category="special",
        unlockable=True,
        description=str(value.get("description") or purpose).strip(),
        template=template,
        sections=sections,
        evidence_requirements=evidence,
    )


def get_specialist(name: str) -> SpecialistDefinition:
    try:
        return SPECIALIST_DEFINITIONS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown specialist: {name}") from exc
