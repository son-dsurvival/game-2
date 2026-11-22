# Specialist Architecture

The runtime has no always-on core specialist categories. Each specialist receives a narrowly scoped Evidence Bundle containing only the information needed for its responsibility.

## Routed Specialist Categories

- **Character-scoped lenses** — each named character may receive unique specialists for identity and behavior, stats, actions and effects, class, and social autonomy. These are routed only when relevant; they are not generic core lanes.
- **Special** — owns unique domains such as a dungeon ecology, civilization, religion, technology branch, relay system, or other unlocked branch. It is routed only when a relevant branch is unlocked.

## Supporting Services

- **Evidence Bundle** — selects and freezes the relevant evidence for the current task. It is context infrastructure, not a specialist.
- **Recorder / Memory State** — stores temporary and durable session information after resolution. It replaces the former mandatory Cache Specialist.
- **Active Skills and Spells** — tracks established active skills and spells for relevant characters.
- **Tier and Level-up** — analyzes XP thresholds, level advancement, and tier progression.
- **Consumables and Rewards** — tracks consumables, loot, rewards, grants, and bookkeeping consequences.
- **Create** — audits unlocked branches and new player-character arrivals for recurring uncovered domains, then proposes a bounded new specialist when needed. It is a meta-process, not an always-on analysis category.
- **Lead Resolver** — reconciles specialist findings and makes the final decision.

There is no mandatory Cache Specialist. Evidence selection, scoped context, and Recorder persistence handle the memory responsibilities that previously belonged to the cache lane. Legacy cache fields may remain in old records for replay compatibility, but new turns do not require or run a cache specialist.

## Routing and Evidence Scope

Routing uses tag profiles rather than treating tags as an unrelated flat list. A profile may add baseline specialists (for example, combat adds Combat, Difficulty, Time, and Modifier analysis) while optional specialists are added only by additional tags such as spell, resource cost, situation, or consequence. `mode.noncombat` and `stakes.low` are control tags and do not own specialists.

A normal turn routes only the leaf specialists required by the action, participating characters, or unlocked branches. Character specialists are unique per named character, while Special specialists are unique per established branch. Create is triggered when branch discovery identifies a candidate or when a new player-character arrival requires a coverage audit.

The Evidence Bundle is scoped separately for each specialist. Each leaf specialist receives only the records, state, rules, and evidence needed for its assigned domain.

Specialists analyze and cite evidence. They do not resolve the final outcome, write campaign files, or silently unlock branches. The Lead Resolver decides; the Recorder persists approved results; the Admin Agent and Admin Editor govern persistent Markdown changes.

`brain/branch_discovery.py` scans lore, rules, Event/Game logs, TEMP_MEMORY, runtime state, conversation history, and specialist findings for recurring uncovered domains. It reports explainable candidates to Create and Lead Resolver. Discovery never unlocks a branch by itself; resolved confirmation and approval remain required.

Create proposals are validated and returned as `created_specialists` with status `proposed`. Approved branch packages are stored by the Admin Editor in the Branch Registry, branch template, `brain/info/specialist_registry.json`, and `brain/info/router_taxonomy/tags.json` as one transaction. Locked branch specialists remain dormant until the branch is unlocked.
