# Specialist Architecture

The runtime has three core analysis categories, not one flat list of equal specialists. Each specialist receives a narrowly scoped Evidence Bundle containing only the information needed for its responsibility.

## Core Analysis Categories

- **Rules** — owns game mechanics and rule interpretation. Its routed leaf specialists cover time, resources, difficulty, XP, modifiers, combat, spells, classes, experimentation, and related rule domains.
- **Character** — owns character-specific analysis. Each named character has a unique character specialist concerned with that character's voice, reactions, motives, modifiers, relationships, participation, consent, and autonomy.
- **Special** — owns unique domains that do not fit ordinary rules or character analysis, such as a dungeon ecology, civilization, religion, technology branch, relay system, or other unlocked branch. Each established branch may receive its own specialist.

## Supporting Services

- **Evidence Bundle** — selects and freezes the relevant evidence for the current task. It is context infrastructure, not a specialist.
- **Recorder / Memory State** — stores temporary and durable session information after resolution. It replaces the former mandatory Cache Specialist.
- **Create** — audits unlocked branches and new player-character arrivals for recurring uncovered domains, then proposes a bounded new specialist when needed. It is a meta-process, not an always-on analysis category.
- **Lead Resolver** — reconciles specialist findings and makes the final decision.

There is no mandatory Cache Specialist. Evidence selection, scoped context, and Recorder persistence handle the memory responsibilities that previously belonged to the cache lane. Legacy cache fields may remain in old records for replay compatibility, but new turns do not require or run a cache specialist.

## Routing and Evidence Scope

A normal turn routes the Rules, Character, and relevant Special categories. Leaf specialists are added only when the action or an unlocked branch requires them. Character specialists are unique per named character, while Special specialists are unique per established branch. Create is triggered when branch discovery identifies a candidate or when a new player-character arrival requires a coverage audit.

The Evidence Bundle is scoped separately for each specialist. A Rules specialist should receive mechanics and relevant state; a character specialist should receive that character's records and relationships; and a Special specialist should receive only the branch lore, state, rules, and evidence needed for that branch.

Specialists analyze and cite evidence. They do not resolve the final outcome, write campaign files, or silently unlock branches. The Lead Resolver decides; the Recorder persists approved results; the Admin Agent and Admin Editor govern persistent Markdown changes.

`brain/branch_discovery.py` scans lore, rules, Event/Game logs, TEMP_MEMORY, runtime state, conversation history, and specialist findings for recurring uncovered domains. It reports explainable candidates to Create and Lead Resolver. Discovery never unlocks a branch by itself; resolved confirmation and approval remain required.

Create proposals are validated and returned as `created_specialists` with status `proposed`. They are not written to campaign files or executed automatically.
