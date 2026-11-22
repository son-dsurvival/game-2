"""Specialist contracts for evidence-backed turn analysis."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import re

from brain.specialists.modifier_contract import MODIFIER_MAGNITUDE_PROMPT


@dataclass(frozen=True)
class SpecialistDefinition:
    """A bounded specialist role.

    ``category`` is the orchestration lane, not a second permission system:
    specialists are routed only when their domain is relevant, while
    ``special`` roles are unlocked by a campaign branch. Keeping this metadata
    beside the prompt makes the registry the single source of truth for
    routing, evidence scoping, and creation.
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
    task_prompt: str = ""
    branch: str | None = None


# No generic specialist is always-on. Evidence Bundle construction and
# Recorder persistence handle context and memory. Leaf specialists are routed
# only for relevant actions or explicitly unlocked branches; Create is routed
# only for an explicit coverage audit.



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
    # Special is not a core lane; it is routed only for relevant unlocked branches.
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
        # BranchRegistry owns activation for individual unlocked branches.
        activation_tags=(),
    ),
    "create": _routed(
        "create",
        (
            "Read the supplied rules, current state, character records, world lore, "
            "and active branch evidence. When a new player character arrives, create "
            "or audit that character's unique character-scoped specialist context for "
            "voice, reactions, motives, modifiers, relationships, participation, "
            "consent, and autonomy. Do not turn a character's hobby or profession "
            "into a global branch specialist. When a branch becomes active, audit "
            "whether the existing leaf specialists and Special branch coverage cover the "
            "new recurring domain. Propose a new bounded branch specialist only when "
            "a genuinely uncovered recurring domain exists, and verify that existing "
            "scopes remain current. This role proposes definitions; it never silently "
            "changes canon or executes a proposal."
        ),
        (
            "When a branch is unlocked or a new player character arrives, is an existing category or leaf specialist insufficient?",
            "Does the new domain need a character-scoped specialist, a Special branch specialist, or only existing coverage?",
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
    ),
    "modifier": SpecialistDefinition(
        "modifier",
        "Calculate current action-side modifiers while keeping Stat, Effect, Class, Equipment, Situation, and assistance sources distinct.",
        (
            "Which action-side modifiers apply?",
            "Which modifier sources are excluded and why?",
            "Do relevant bonuses sum unless an explicit rule restricts stacking?",
        ),
        category="special",
    ),
    "relationship": SpecialistDefinition(
        "relationship",
        "Track relationship scores, relationship dynamics, trust, bonds, consent, and relationship changes.",
        (
            "What relationship score and dynamics are established?",
            "What relationship change is supported by this interaction?",
            "What consent, boundary, or disagreement facts must be preserved?",
        ),
        ("context.relationship", "context.emotional"),
        category="character",
    ),
    "npc_autonomy": SpecialistDefinition(
        "npc_autonomy",
        "Preserve independent NPC agency, participation, consent, refusal, and autonomous goals.",
        (
            "What does this character choose or refuse independently?",
            "What consent, boundary, or directive applies?",
            "What autonomous consequence follows without deciding for the player?",
        ),
        ("participant.companion", "mechanic.consent"),
        category="character",
    ),
    "cognitive_assistance": SpecialistDefinition(
        "cognitive_assistance",
        "Analyze assistance from linked minds, archives, software, relays, or other cognitive systems.",
        (
            "What assistance is available and linked?",
            "What information, time, cost, and limits apply?",
            "Does the assistance change the action or only provide information?",
        ),
        ("mechanic.cognitive_assistance",),
        category="special",
    ),
    "class": SpecialistDefinition(
        "class",
        "Analyze class identity, class progression, class slots, and Class Modifiers.",
        (
            "What class identity and progression rules apply?",
            "Which class slot or Class Modifier is relevant?",
            "What evidence supports class advancement or a class-specific capability?",
        ),
        ("context.class_system",),
        category="character",
    ),
    "spell": SpecialistDefinition(
        "spell",
        "Analyze established spells and spell creation, including activation, costs, limits, and risks.",
        (
            "What spell or magical operation is established?",
            "What activation, resource, time, and limitation rules apply?",
            "What evidence supports creating or improving the spell?",
        ),
        ("mechanic.spell_creation", "context.skills_spells"),
        category="special",
    ),
    "situation": SpecialistDefinition(
        "situation",
        (
            "Analyze action-side situation modifiers that come from the current "
            "environment and conditions rather than from a character: terrain, "
            "weather, light, visibility, noise, cover, crowding, hazards, timing, "
            "position, and other established situational advantages or penalties."
        ),
        (
            "Which current environmental or situational conditions affect the action?",
            "Which situation modifiers are included, excluded, or zero, and why?",
            "What evidence or observation is missing before a situation modifier can apply?",
        ),
        ("context.situation", "context.environmental", "context.unknown_area", "stakes.field_risk"),
        category="special",
    ),
    "difficulty": SpecialistDefinition(
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

    "resources": SpecialistDefinition(
        "resources",
        "Analyze required, consumed, available, and efficiency-modified resources.",
        ("What resources are required?", "What is consumed?", "Are sufficient resources evidenced?"),
        ("mechanic.resource_cost",),
    ),

    "create_stat_modifier": SpecialistDefinition(
        "create_stat_modifier",
        (
            "Design character-specific starting or earned Stat Modifier options from the "
            "character's stated life, demonstrated capability, meaningful practice, and "
            "the supplied evidence. For every available Stat Modifier slot, "
            "return exactly three distinct choices, grouped contiguously. "
            "If the character has no established basis, generic assumed options are "
            "allowed only when clearly marked as low-basis assumptions; they are not "
            "established facts. More independent demonstrated bases may justify a "
            "higher magnitude within the supplied tier band. Never grant raw stats, "
            "invent history, or bypass the universal stat-modifier laws. Stat Modifiers "
            "must remain broad stat-specific capabilities, not weapon-, class-, or "
            "single-action-specific effects. Every option must declare breadth as "
            "broad_stat_domain and describe the general stat capability across multiple "
            "relevant situations; a tool, room, maneuver, profession, combat exchange, "
            "or single task belongs to Effect Modifiers, not Stat Modifiers. STR can "
            "support general force production; INT general analysis, pattern recognition, "
            "noticing flaws, and problem solving; AGI general movement and coordination; "
            "END general defense and endurance; WIS general awareness, concentration, or "
            "mana control; PRE general charisma. Each option must state the affected stat, "
            "breadth, basis level, major/minor classification, "
            "magnitude, evidence, limits, growth or conversion rule, and any interaction or overlap rule only when "
            "the supplied evidence explicitly supports it. Never invent a no-stacking "
            "or highest-single exclusion; the universal rule is to sum all relevant "
            "bonuses unless a specific rule says otherwise. "
            + MODIFIER_MAGNITUDE_PROMPT
        ),
        (
            "Which character evidence supports a Stat Modifier or a no-modifier choice?",
            "Which broad stat domain, basis level, major/minor classification, magnitude, limits, and growth rule apply?",
            "Does any supplied rule explicitly limit stacking or overlap, or should relevant bonuses sum normally?",
            "Does the character have enough evidence for a high-basis option, or should this be a low-basis generic assumption?",
            "What three distinct options should be offered for each available Stat Modifier slot without inventing history or violating tier rules?",
        ),
        ("mechanic.modifier_creation", "stakes.breakthrough"),
        category="character",
    ),
    "create_effect_modifier": SpecialistDefinition(
        "create_effect_modifier",
        (
            "Design character-specific starting or earned reusable Effect Modifier options "
            "from the character's stated life, demonstrated capability, meaningful practice, "
            "player-authored design brief, and supplied evidence. Ordinary designs return "
            "exactly five distinct valid choices; the setup Effect Modifier batch instead "
            "has ten starting choices from which the player selects three. Each setup choice is "
            "grounded by character tier and labeled high, low, or assumed_low basis. "
            "A player may request something novel; novelty is not "
            "a violation by itself. Do not grant the modifier or invent history. Every "
            "option must include activation conditions, limitations, anti-farming boundary, "
            "stacking behavior, and evidence-backed Modifier Group placement. "
            + MODIFIER_MAGNITUDE_PROMPT
        ),
        (
            "What character history, current design brief, or meaningful achievement supports an Effect Modifier?",
            "Is each effect stable, narrow, reusable, non-duplicative, and compatible with tier and material rules?",
            "What ten distinct options, limitations, activation conditions, placements, and upgrade paths can the player choose three from?",
        ),
        ("mechanic.modifier_creation", "stakes.breakthrough"),
        category="character",
    ),
    "tier_level_up": SpecialistDefinition(
        "tier_level_up",
        "Analyze XP thresholds, level advancement, tier progression, and the evidence required for advancement.",
        (
            "Which XP track and threshold apply?",
            "Has the character met the requirements for a level-up or tier advancement?",
            "What benefits, choices, limits, and unresolved requirements follow from the advancement?",
        ),
        ("mechanic.xp", "context.class_system", "context.tier6"),
        category="special",
    ),
    "consumables_rewards": SpecialistDefinition(
        "consumables_rewards",
        "Track consumable use, replenishment, rewards, loot, grants, and their bookkeeping consequences.",
        (
            "What consumable or reward is created, spent, received, or lost?",
            "What quantity, condition, source, destination, and limitation apply?",
            "Does the reward affect XP, resources, equipment, a facility, or another record?",
        ),
        ("mechanic.resource_cost", "mechanic.reward"),
        category="special",
    ),
    # Compatibility name for saved routes and old records. New setup and
    # routing use the two typed character specialists above.

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
    "consequences": SpecialistDefinition(
        "consequences",
        "Identify possible irreversible, factional, visibility, relationship, and world consequences without resolving them.",
        ("What could become irreversible?", "Which people, factions, or systems could be affected?", "What consequence evidence is missing?"),
        ("stakes.irreversible", "stakes.contested", "stakes.field_risk"),
    ),

}

# Legacy domain roles remain available as explicit, finer-grained specialists.
# They are routed only when their domain is relevant. This preserves existing
# saved routes while making unlockability explicit for new campaigns.

# Specialist-specific model instructions live with the specialist registry so
# each role owns its own contract. The runner supplies only the selected role's
# task prompt; unrelated lanes are not injected into every model call.
_SPECIALIST_TASK_PROMPTS = {
    "modifier": """Own current action-side modifier breakdown only. Keep Stat, Effect, Class, Equipment, Situation, and assistance modifiers distinct. Include only modifiers whose scope matches the declared action. Do not create or award modifiers.""",
    "relationship": """Own relationship score, relationship dynamics, trust, bonds, consent, boundaries, and relationship changes only. Preserve disagreement and refusal; do not assume a relationship outcome.""",
    "npc_autonomy": """Own NPC autonomy, participation, consent, refusal, and independent goals only. Do not decide for the player or assume cooperation.""",
    "cognitive_assistance": """Own cognitive assistance from linked systems, archives, software, relays, or minds only. Track information, time, cost, and limits without resolving the action.""",
    "class": """Own class identity, class progression, class slots, and Class Modifiers only. Do not grant advancement or select a Class Modifier.""",
    "spell": """Own established spells and spell creation only. Track activation, costs, time, limits, evidence, and risks. Do not invent or award a spell.""",
    "situation": """Own situation modifiers only. Analyze established environmental and action conditions such as terrain, weather, light, visibility, noise, cover, crowding, hazards, timing, and position. Keep these distinct from Stat, Effect, Class, Equipment, assistance, and character modifiers. Include a modifier only when its scope matches the declared action; use zero or exclusion with a reason when it does not. Do not invent environmental facts, resolve the action, or change the world state.""",
    "difficulty": """Own difficulty and task-side target calculation. Add the same `calculation` difficulty contract when required. Do not calculate Action Value or resolve the outcome.""",
    "modifier": """Own current action-side modifier breakdown only. Keep Stat, Effect, Class, Equipment, Situation, and assistance modifiers distinct. Include only modifiers whose scope matches the declared action. Add `calculation` only when the modifier calculation contract is required; do not create or award modifiers.""",
    "world": """Own world-event and world-pool mechanics only. When generating an event, add `world_event` with roll, selected_trigger, pool_adjustments, event_tier, generated_event, encounter_condition, and latest_phase. When preparing a pool, add `world_pool` whose trigger lists partition 1–100 exactly once. Do not place world-event work in another specialist's response.""",
    "create_stat_modifier": """Own Stat Modifier design only. Identify every eligible stat slot and return exactly three contiguous `stat_modifier_options` per slot. Each option requires name, stat, tier, breadth=`broad_stat_domain`, basis_level (high/low/assumed_low), major_or_minor, magnitude, description, evidence, limitations, and growth_or_conversion_rule. Every option must be a broad capability across multiple relevant situations; tools, rooms, professions, maneuvers, combat exchanges, and single tasks belong to Effect Modifiers. Do not award or select an option. """ + MODIFIER_MAGNITUDE_PROMPT,
    "create_effect_modifier": """Own Effect Modifier design only. Ordinary requests return exactly five `effect_modifier_options`; setup batch `status_effect_modifiers` returns exactly ten and the player selects three. Each option requires basis_level, tier, magnitude, description, boost_domain, evidence, activation_conditions, limitations, anti_farming_boundary, stacking, and placements. Do not create Stat or Class Modifiers and do not award or select an effect. """ + MODIFIER_MAGNITUDE_PROMPT,
    "class": """Own class and Class Modifier rules only. For setup batch `status_class_modifiers`, identify available class slots and return exactly five contiguous `class_modifier_options` per slot. Each requires slot, name, class, tier, basis_level, magnitude, description, evidence, activation_conditions, and limitations. Do not grant a class or choose an option. """ + MODIFIER_MAGNITUDE_PROMPT,
    "tier_level_up": """Own XP thresholds, level advancement, and tier progression only. Identify the applicable XP track, threshold, evidence, benefits, choices, and unresolved requirements. Recommend advancement when supported; do not silently award XP or mutate the character.""",
    "consumables_rewards": """Own consumables, rewards, loot, grants, replenishment, and bookkeeping consequences only. Track quantities, sources, destinations, limits, and whether an outcome belongs in the resource ledger, equipment, XP, or another record. Do not invent rewards or apply changes.""",
    "create": """Own bounded specialist discovery only. Add `created_specialists` only for a safe, recurring uncovered branch or a newly named character. Each proposal requires lowercase snake-case name, purpose, questions, and activation_tags. Discovery proposes; it does not unlock or install. Do not perform world, modifier, or character analysis unless explicitly assigned to that scope.""",
}



for _name, _task_prompt in _SPECIALIST_TASK_PROMPTS.items():
    if _name in SPECIALIST_DEFINITIONS:
        SPECIALIST_DEFINITIONS[_name] = replace(
            SPECIALIST_DEFINITIONS[_name], task_prompt=_task_prompt
        )

SPECIALIST_GROWTH_NOTE = (
    "Special is routed only for relevant unlocked branches. Create audits new "
    "player-character arrivals and unlocked branches for genuinely recurring "
    "uncovered domains, proposes bounded definitions, and checks that existing "
    "scopes stay current."
)

_CREATED_NAME = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
RETIRED_SPECIALIST_NAMES = frozenset({"rules", "character"})
SPECIALIST_CATALOG_PATH = Path(__file__).resolve().parents[1] / "info" / "specialist_registry.json"


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
        or name in RETIRED_SPECIALIST_NAMES
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
        branch=(str(value.get("branch")).strip() if value.get("branch") else None),
    )


def register_specialist(definition: SpecialistDefinition) -> SpecialistDefinition:
    """Register a runtime specialist definition in the in-memory registry.

    Character-scoped specialists are created from approved character records,
    so their definitions are registered at runtime rather than hard-coded as
    global lanes. Existing global definitions cannot be silently replaced.
    """
    if not isinstance(definition, SpecialistDefinition):
        raise TypeError("definition must be a SpecialistDefinition")
    existing = SPECIALIST_DEFINITIONS.get(definition.name)
    if existing is not None and existing != definition:
        raise ValueError(f"Specialist already registered with different definition: {definition.name}")
    SPECIALIST_DEFINITIONS[definition.name] = definition
    return definition


def get_specialist(name: str) -> SpecialistDefinition:
    try:
        return SPECIALIST_DEFINITIONS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown specialist: {name}") from exc


def _load_persisted_specialists() -> None:
    """Load approved branch specialists without activating locked branches."""
    try:
        raw = json.loads(SPECIALIST_CATALOG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return
    values = raw.values() if isinstance(raw, dict) else raw if isinstance(raw, list) else []
    try:
        from brain.specialists.branch_registry import BranchRegistry
        branches = BranchRegistry(SPECIALIST_CATALOG_PATH.parents[2])
    except (ImportError, OSError):
        branches = None
    for item in values:
        if not isinstance(item, dict):
            continue
        branch = str(item.get("branch") or "").strip() or None
        if branch and branches is not None and not branches.is_unlocked(branch):
            continue
        definition = validate_created_definition(item)
        if definition is None:
            continue
        if branch:
            definition = replace(definition, branch=branch)
        task_prompt = _SPECIALIST_TASK_PROMPTS.get(definition.name)
        if task_prompt:
            definition = replace(definition, task_prompt=task_prompt)
        try:
            register_specialist(definition)
        except ValueError:
            continue


_load_persisted_specialists()
