# Terms and Nomenclature

This document describes the campaign runtime commands, state gates, and major technical processes. It is an administrative reference, not roleplay canon.

## Runtime Command Reference

| Command | Function |
| --- | --- |
| `/help` | Displays all available commands. |
| `/status` | Shows the current phase, play gate, pending operation, and saved stage. |
| `/retry` | Restarts the failed task from the beginning of its pipeline. |
| `&#123;pause&#125;` | Stops roleplay and places the runtime in outside-game mode. |
| `&#123;resume&#125;` | Resumes roleplay from an explicit pause, approved new game, or approved new day. |
| `/new-game` | Starts a new campaign setup flow. |
| `/new-character` | Drafts an additional player character. |
| `/new-party-member` | Drafts an NPC party member. |
| `/add` | Adds another character during setup. |
| `/main NAME` | Selects the party's main player character. |
| `/review` | Prepares the current setup for review. |
| `/approve` | Approves a normal administrative proposal. |
| `/approve-reset` | Explicitly approves replacement of the current campaign. |
| `/cancel-setup` | Cancels setup without destroying the active campaign. |
| `/end-day` | Starts rest and day-end processing. |
| `/specialists` | Lists stored specialist proposals. |
| `/install NAME` | Proposes installing an approved specialist. |
| `/quit` | Exits while preserving resumable state. |
| `OOC request` | A request enclosed in curly braces sends an out-of-roleplay administrative request. |

## Runtime State Gates

### `setup_required`

No active campaign exists. New-game setup must begin before roleplay can open.

### `setup_draft`

The player is drafting characters, party members, identity, stats, backgrounds, and the main character.

### `setup_review`

The setup proposal is ready for review. Campaign documents have not been replaced.

### `awaiting_clarification`

The current operation is paused until the player answers a required question.

### `awaiting_dice`

The Lead Resolver requires a saved dice result before resolution can continue.

### `day_end_review`

The completed day has been prepared for review. Normal next-day play is blocked until approval.

### `world_event_pending`

The approved day has ended and the next-day world-event roll/event stage is being completed.

### `new_game_pending`

New-game Markdown changes have been approved and stored. Roleplay cannot begin until the player uses `&#123;resume&#125;`.

### `new_day_pending`

Day-end changes and next-day event preparation are complete. Roleplay remains outside the game until the player uses `&#123;resume&#125;`.

### `paused`

The player explicitly paused roleplay. Plain text is treated as outside-game administrative text until `&#123;resume&#125;`.

### `open`

Normal gameplay may proceed.

### `retry`

A failure stopped the current operation safely. `/retry` restarts that task from its pipeline entry stage rather than continuing the failed checkpoint.

## New-Game Setup Process

```text
/new-game
→ character draft
→ party draft
→ main-character selection
→ setup specialist review
→ document proposal
→ player approval
→ Admin Editor
→ campaign initialization
→ `new_game_pending`
→ player uses `&#123;resume&#125;`
→ opening scene
```

The setup review includes class, world, and typed modifier design. Create Stat Modifier produces three bounded choices per available Stat Modifier slot. Create Effect Modifier produces ten bounded choices, from which the player selects three; the player selections are required before the approved result is persisted.

## Normal Turn Process

```text
player input
→ Turn Router identifies the process and action segments
→ exact leaf-specialist activation plan
→ scoped Evidence Bundles
→ only relevant Rules, Character, and Special leaf instances
→ Coverage Check
→ Lead Resolver
→ dice or clarification continuation when required
→ Narrator
→ Session Recorder
→ background phase processing
→ saved checkpoint
```

The category names are organizational boundaries, not automatic model calls. No specialist lane is always-on; the Turn Router selects only the leaf specialists required by the action, participating characters, or an unlocked branch. Specialists analyze; the Lead Resolver decides; the Narrator reveals only approved visible information; the Recorder persists temporary session state.

### In-World Discussion Process

```text
player speaks, asks, explains, argues, or plans in-world
→ Turn Router marks `in_world_discussion`
→ participating character state
→ NPC Autonomy, Relationships, Consent, or Cognitive Assistance when relevant
→ relevant unlocked branch specialist, if any
→ Lead Resolver resolves the conversation
→ Narrator presents the response
```

An in-world discussion does not activate combat, resource, modifier-creation, or Create specialists unless the player commits to an actual action or explicitly requests a design. Discussion routes concrete character leaf specialists rather than retired generic category placeholders.

## Assumption and Initialization Process

```text
missing mechanism or starting value
→ relevant leaf specialist reports the gap
→ player authorizes delegation, such as “you decide”
→ Assumption & Initialization Wizard creates a bounded provisional record
→ Lead Resolver applies it only within its declared scope
→ Recorder stores it in TEMP_MEMORY.md
→ repeated use triggers Create and Admin Agent audit
→ player approval and Admin Editor are required for permanent promotion
```

A provisional rule, starting value, or reward seed is not permanent canon. The Wizard may use an established rule band, a real-world baseline, or the nearest supported comparison, but it must state its basis, limitations, confidence, scope, and review trigger. Existing rules always take priority over an assumption.

## Explicit Pause and Resume Process

```text
open roleplay
→ player writes `&#123;pause&#125;`
→ paused outside-game mode
→ plain text is treated as administrative text
→ player writes `&#123;resume&#125;`
→ open roleplay
```

A new game and an approved day end use the same outside-game boundary. Approval stores the Markdown changes first; `&#123;resume&#125;` is required before the next roleplay section begins.

## Administrative Request Process

```text
OOC request
→ outside-game routing
→ evidence and specialist review
→ answer or exact edit proposal
→ proposal version binding
→ player approval
→ Admin Editor
→ atomic write and audit receipt
```

`admin_agent.py` reasons and proposes. It does not write files. `admin_editor.py` applies only an approved, version-checked proposal.

## Day-End Process

```text
end of day
→ completed-day records
→ branch discovery
→ modifier review
→ world-pool review
→ Admin Agent proposal
→ player approval
→ Markdown promotion
→ evidence-index refresh
→ saved d100 world-event roll
→ pending event with encounter condition/deadline
→ `new_day_pending`
→ player uses `&#123;resume&#125;`
→ next-day play
```

Branch discovery records candidates but does not activate specialists. Only a confirmed and approved branch becomes `status: unlocked` in the Branch Registry.

## Modifier Taxonomy

- **Stat Modifier:** broad stat-specific support, not a weapon- or single-action-specific effect. Examples: INT analysis, pattern recognition, and noticing flaws; WIS mana control; AGI movement and coordination; STR forceful swings, strikes, pushes, or lifts; END defense and endurance; and PRE charisma.
- **Effect Modifier:** action- or technique-specific support. Examples: swordplay, magic, and programming.
- **Class Modifier:** class-specific support. Examples: Swordsman swordplay and Mage spells.

These types remain distinct but may all apply to the same action when relevant. Their bonuses sum under the normal relevant-bonus rule unless an explicit rule says otherwise.

## Modifier-Creation Process

```text
character history / player design brief / experiments / training
→ typed modifier specialist
→ three Stat Modifier choices per Stat Modifier slot, ten Effect Modifier choices with three selected, or five Class Modifier choices per Class Modifier slot
→ player selects one option per Stat/Class slot or three Effect options
→ relevant difficulty, modifier, and class specialists validate legality and stacking
→ Lead Resolver confirms the selection
→ Admin Agent and Admin Editor persist the approved result
```

The ordinary Modifier specialist calculates current action-side modifiers. Each character has typed creation specialists: Create Stat Modifier generates three choices per available stat slot, Create Effect Modifier generates ten reusable effect choices from which three are selected, and Class Modifier setup generates five class-specific choices per available class slot, all with evidence, limitations, activation conditions, stacking, and group placement.

## Specialist and Resolution Responsibilities

| Component | Responsibility |
| --- | --- |
| Turn Router | Classifies the request and selects lanes. |
| Evidence Bundle | Freezes relevant source evidence. |
| Routed Leaf Specialists | Analyze only the mechanics, character, social, world, modifier, and branch domains required by the current task. |
| Character-scoped Specialists | Analyze relevant named-character contexts without using a generic Character lane. |
| Special Specialist | Monitors unlocked branches. |
| Create Specialist | Proposes missing specialist scopes. |
| Active Skills and Spells Specialist | Tracks established active skills and spells, including activation, costs, limits, and progression. |
| Tier and Level-up Specialist | Analyzes XP thresholds, level advancement, tier progression, and advancement requirements. |
| Consumables and Rewards Specialist | Tracks consumables, rewards, loot, grants, replenishment, and bookkeeping consequences. |
| Modifier Specialist | Calculates current action modifiers. |
| Create Stat Modifier Specialist | Generates three character-grounded Stat Modifier choices per available slot for player selection. |
| Create Effect Modifier Specialist | Generates ten character-grounded Effect Modifier choices, from which three are selected, with evidence, limitations, activation, stacking, and group placement. |
| Class Modifier Setup | Generates five class-specific choices per available Class Modifier slot; the player selects one per slot. |
| Lead Resolver | Makes the final mechanical and fictional decision. |
| Narrator | Converts visible resolution data into player-facing prose. |
| Recorder | Stores temporary session facts and promotion records. |
| Admin Agent | Answers OOC questions and prepares defended edit proposals. |
| Admin Editor | Applies approved Markdown changes atomically. |

## Markdown File Reference

| Markdown file | What it stores |
| --- | --- |
| `Branch Registry.md` | Discovered branch candidates, activation status, specialist names, activation tags, evidence sources, and unlock reasons. Only `status: unlocked` branches are routed. |
| `character relationship.md` | Character and party-member relationships, trust, bonds, consent, autonomy, relationship tiers, and relationship changes. |
| `Experimentation Register.md` | Player-readable OOC experiments, completed experiments, safe background status, and approved outside-player-perspective updates. Private surprises remain in backend state. |
| `game rules (1).md` | Core game mechanics: time, phases, travel, world events, combat, noncombat actions, resources, stats, modifiers, skills, XP, tiers, NPC autonomy, relationships, and party rules. |
| `Ledger Resources.md` | Character and party resources such as money, HP, MP, SP, food, water, materials, equipment, consumables, and other tracked supplies. |
| `status sheet.md` | Character identity, stats, class, levels, tier, derived values, stat/class/effect modifiers, skills, and equipment. |
| `TEMP_MEMORY.md` | Temporary session position, cache, active threads, commitments, unresolved questions, expiring facts, pending canon, and temporary branch records. |
| `TERMS_AND_NOMENCLATURE.md` | Technical command reference, runtime state gates, pipeline processes, component responsibilities, storage boundaries, and Markdown file descriptions. |
| `🌍 CORE WORLD FRAME (REFINED).md` | Canon world lore, System laws, Earth Upgrade history, dungeons, peoples, classes, technology, Bases, civilizations, currency, Tier-6 entities, Event log, and Game log. |

## Markdown Storage Boundary

Persistent Markdown information must pass through the outside-game Admin Agent and approved Admin Editor before it is written.

The normal exceptions are:

- `markdown_files/TEMP_MEMORY.md`, which is Recorder-owned temporary session memory;
- the approved party-member backend setup task.

Private runtime state remains under `brain/state/` and is not player-facing canon.
