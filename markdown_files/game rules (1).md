# Game rules

## ⏳ TIME S:YSTEM

### 1. Phase Structure

A full day is divided into **9 Phases**:

1. Early Morning
2. Morning
3. Late Morning
4. Midday
5. Mid Afternoon
6. Late Afternoon
7. Evening
8. Night
9. Midnight

Each phase is a **fixed unit of meaningful activity time**.



### 2. Outside Phase Rule (Major Actions)

Any **major activity consumes Phase Time**.

**Definition:<br> **A task that requires focus, effort, or progression.

**Examples:**

●      Studying (books, skills, systems)

●      Crafting / building

●      Alchemy / engineering

●      Gathering (herbs, materials)

●      Hunting / combat operations

●      Long-distance travel

●      Negotiations / formal meetings

●      Research / experimentation

**Rule:<br> **→ 1 major activity = **1 Phase consumed** (unless modified)



### 3. Within Phase Rule (Minor Actions)

Minor actions occur **inside a phase** and do not consume additional time.

**Definition:<br> **Low-impact, short-duration, or support actions.

**Examples:**

●      Conversations

●      Meals

●      Planning

●      Equipment preparation

●      Giving instructions

●      Quick inspections

●      Inventory management

**Rule:<br> **→ Unlimited within-phase actions allowed **as long as they do not escalate into major tasks**



### 4. Combat Time Rule

Combat is **time-compressed for pacing**.

●      1 Combat Encounter = **0.5 Phase**

●      2 Encounters = **1 Phase**

●      3 Encounters = **1.5 Phases**

**Rule:**

●      Phase cost is tracked cumulatively

●      Rounding only occurs **after the scene ends**



**Note: **

- A combat encounter is different from a combat turn A combat encounter ends when all enemies are dead or after 20 combat turn
- Every 5 combat turn cost 1 sp but some effects can reduce the sp cost



### 5. Travel Rule

Travel cost depends on **distance and difficulty**:

●      **Short Distance** → Within current phase (no cost)

●      **Moderate Distance** → 0.5 Phase

●      **Long Distance** → 1 Phase (or more if extreme)



### 6. Phase Carryover Rule

Related actions are grouped into a **single phase** when logically continuous.

**Example:**

●      Hunt → Kill → Harvest → Move within zone<br> → Counts as **1 Phase**, unless duration clearly exceeds limits



### 7. Phase Tracking Rule

After every major scene, always state:

●      Current Phase

●      Phase(s) Consumed

●      Next Phase

**Purpose:<br> **→ Prevent time drift<br> → Maintain system integrity

### ⚙️ SYSTEM INTENT

This structure ensures:

●      Time remains **trackable and enforceable**

●      Actions have **clear cost**

●      The world reacts **dynamically, not statically**

●      Routine is punished with **disruption pressure**



## 🌍 Dynamic World Event Engine

### 1. Core Purpose

The Dynamic World Event Engine adds variety, opportunities, complications, and unexpected developments to the game.

It uses a changing **number pool** to determine what type of event occurs.

Player actions, party actions, NPC activity, environmental changes, and unresolved conditions can increase or reduce the chance of particular events.

The pool must reflect the current world state.

### 2. Event Triggers

An **Event Trigger** is an event category.

Default triggers include:

| Event Trigger | Possible Events |
|---|---|
| **Monsters** | Sightings, attacks, migrations, nests, unusual behavior, or hunting opportunities |
| **Business** | Customers, trade opportunities, shortages, competition, theft, or market changes |
| **People** | Visitors, requests, disputes, recruitment, rumors, faction contact, or personal encounters |
| **Weather** | Rain, storms, heat, fog, favorable conditions, or unusual weather |
| **Nothing** | No new event is generated at this check |

A trigger determines the **type of event**, not whether it is beneficial or harmful.

Additional triggers may be introduced when the setting requires them. Each new trigger must represent a distinct category and receive its numbers from existing pools.

### 3. The Number Pool

The engine uses the numbers **1–100**.

Each Event Trigger owns an explicit list of numbers, written like this:

`[1, 2, 3]`

Each owned number represents a **1% chance** of activating that trigger.

#### Pool Rules

- Each number belongs to exactly one trigger.
- All pools together must contain every number from **1–100**.
- No number may appear in more than one pool.
- Numbers do not need to be consecutive.
- A trigger with an empty pool, `[]`, has a **0% chance**.
- Every pool must be displayed as an explicit list of its owned numbers.

#### Example Starting Pool

| Event Trigger | Number Pool | Chance |
|---|---|---:|
| Monsters | [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45, 49, 53, 57, 61, 65, 69, 73, 77] | 20% |
| Business | [2, 6, 10, 14, 18, 22, 26, 30, 34, 38, 42, 46, 50, 54, 58, 62, 66, 70, 74, 78] | 20% |
| People | [3, 7, 11, 15, 19, 23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63, 67, 71, 75, 79, 81, 85, 89, 93, 97] | 25% |
| Weather | [4, 8, 12, 16, 20, 24, 28, 32, 36, 40] | 10% |
| Nothing | [44, 48, 52, 56, 60, 64, 68, 72, 76, 80, 82, 83, 84, 86, 87, 88, 90, 91, 92, 94, 95, 96, 98, 99, 100] | 25% |
| **Total** | **100 unique numbers** | **100%** |

This is an example distribution. The actual starting distribution depends on the location and established world conditions.

### 4. Changing the Pool

The pool changes when actions or developments meaningfully affect the likelihood of an event category.

| Development | Possible Pool Change |
|---|---|
| Leaving monster remains near camp | Monsters gains numbers |
| Destroying a nearby monster nest | Monsters loses numbers |
| Advertising a shop or opening a trade route | Business gains numbers |
| Suspending business operations | Business loses numbers |
| Gaining a public reputation | People gains numbers |
| Moving into an isolated location | People may lose numbers |
| An approaching storm front | Weather gains numbers |
| Conditions becoming stable and quiet | Nothing may gain numbers |

Every adjustment must have a clear cause.

An action only affects categories it can reasonably influence. Ordinary actions cannot alter weather probability unless they change exposure to weather events or involve an established ability to influence weather.

A category gaining numbers does not automatically mean increased danger. It may represent increased opportunity, activity, attention, or instability.

### 5. Number Transfer Rule

The combined pool must always contain exactly **100 numbers**.

Whenever one trigger gains numbers, another trigger must lose those exact numbers.

Numbers may transfer:

- From **Nothing** to an increasingly likely event category.
- From a less likely event category to **Nothing**.
- Between event categories when pressure or opportunity changes form.

A trigger cannot give away numbers it does not own.

#### Example: Advertising a Shop

Business gains five numbers from Nothing.

**Transferred numbers:**

`[44, 48, 52, 56, 60]`

**Business — Before:**

`[2, 6, 10, 14, 18, 22, 26, 30, 34, 38, 42, 46, 50, 54, 58, 62, 66, 70, 74, 78]`

**Business — After:**

`[2, 6, 10, 14, 18, 22, 26, 30, 34, 38, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 66, 70, 74, 78]`

**Nothing — Before:**

`[44, 48, 52, 56, 60, 64, 68, 72, 76, 80, 82, 83, 84, 86, 87, 88, 90, 91, 92, 94, 95, 96, 98, 99, 100]`

**Nothing — After:**

`[64, 68, 72, 76, 80, 82, 83, 84, 86, 87, 88, 90, 91, 92, 94, 95, 96, 98, 99, 100]`

Business increases from **20% to 25%**. Nothing decreases from **25% to 20%**.

### 6. Adjustment Size and Duration

The size of a pool adjustment depends on:

- The scale of the action or development.
- Its actual success or failure.
- The people, creatures, locations, or systems affected.
- Whether its consequences are temporary or lasting.
- Existing conditions that strengthen or weaken its effect.

Apply changes after the relevant outcome is established.

**An unchanged condition does not repeatedly add numbers at every check.** Further adjustments require a new development or a genuine increase or decrease in its influence.

Temporary adjustments must record when or under what conditions they end. When they expire, reverse their recorded transfers unless a newer world-state change justifies a different distribution.

Persistent adjustments remain until their cause changes.

### 7. Event Check Timing

Make **one event check at the start of each game day**.

Additional checks may occur after:

- Entering a substantially different location.
- Completing a major operation that changes local conditions.
- Reaching another meaningful story transition.

Minor actions do not automatically cause additional checks.

Do not make repeated checks for the same unchanged situation merely to force an event.

### 8. Event Roll Procedure

At each event check:

1. Review the current location and world state.
2. Apply justified pool changes.
3. Confirm that every number from **1–100** has exactly one owner.
4. Roll **1d100** once.
5. Identify the Event Trigger that owns the rolled number.
6. If the trigger is **Nothing**, introduce no new event.
7. Otherwise, determine the event’s tier and specific circumstances.
8. Present the event and resolve any player response through the normal game rules.
9. Record resulting world-state changes.

**Do not reroll because the result is inconvenient or uneventful.**

### 9. Event Tier Rule

Every event generated by the pool must be either:

- **The same tier as the player’s current character tier**, or
- **Exactly one tier higher than the player’s current character tier**.

Use the player character’s tier at the time of the check.

| Player’s Current Tier | Allowed Event Tiers |
|---|---|
| Tier 0 | Tier 0 or Tier 1 |
| Tier 1 | Tier 1 or Tier 2 |
| Tier 2 | Tier 2 or Tier 3 |
| Tier 3 | Tier 3 or Tier 4 |
| Tier 4 | Tier 4 or Tier 5 |
| Tier 5 | Tier 5 or Tier 6 |
| Tier 6 | Tier 6 |

Choose between the allowed tiers based on established world conditions, accumulated pressure, and the nature of the event. Record the reason for selecting the higher tier.

The event’s tier represents its overall scale, demands, or consequences. It does not require every person, creature, or object involved to have that tier.

**Pool size determines frequency, not tier.**

The **Nothing** result has no event tier.

### 10. Generating the Specific Event

The selected trigger determines the category. Current circumstances determine what happens within that category.

Consider:

- Location and environment.
- Recent actions and consequences.
- Nearby NPCs, factions, businesses, and creatures.
- Existing opportunities and unresolved problems.
- Established capabilities and dangers.
- The allowed event tier.

Events may be beneficial, harmful, mixed, or initially unclear.

Events must give the player something to encounter, respond to, investigate, exploit, prepare for, or ignore.

An event does not automatically dictate the player’s response or guarantee an outcome. Actions taken during the event follow normal validity, time, resource, and resolution rules.

### 11. Nothing Result

If the roll selects **Nothing**, no new event is introduced by that check.

Existing conditions continue:

- Current threats remain active.
- Scheduled events still occur.
- NPCs continue established plans.
- Weather and environmental conditions continue normally.
- Previously started consequences continue developing.

Nothing allows space for ordinary play, preparation, recovery, and player-directed activity.

### 12. Events Outside the Pool

The pool governs uncertain new developments.

Established consequences occur when their conditions are met. A scheduled visitor can arrive, an ongoing storm can continue, and a known enemy can carry out an established attack without winning another event roll.

Do not use **Nothing** to cancel an established event.

The event tier restriction applies to **new events generated by this engine**. Existing world facts and ongoing events retain their established properties.

### 13. Tracking and Transparency

At every event check, display the current pool:

| Event Trigger | Current Number Pool | Chance |
|---|---|---:|
| Monsters | [explicit owned numbers] | — |
| Business | [explicit owned numbers] | — |
| People | [explicit owned numbers] | — |
| Weather | [explicit owned numbers] | — |
| Nothing | [explicit owned numbers] | — |
| **Total** | **100 unique numbers** | **100%** |

Also record:

| Field | Required Information |
|---|---|
| Check timing | Current day, phase, and reason for the check |
| Pool adjustments | Numbers transferred, source, destination, and cause |
| Duration | Expiry condition for temporary adjustments |
| Roll | Actual d100 result |
| Selected trigger | Category owning the rolled number |
| Player tier | Current character tier |
| Event tier | Same tier or one tier higher; none for Nothing |
| Generated event | Specific development and its immediate circumstances |

No hidden pool changes, duplicate numbers, missing numbers, or unrecorded rerolls are allowed.

### Core Principle

**Actions change the odds. The roll selects the event category. World conditions shape the event within the allowed tier range.**## Resting Rules

### 1. Rest Recovery by Duration

Restoration of **HP, MP, and SP** depends on the total duration of uninterrupted rest.



| **Rest Duration** | **Recovery** |
| --- | --- |
| 0.5 Phase Rest | Restores 25% of maximum HP, MP, and SP |
| 1 Phase Rest | Restores 50% of maximum HP, MP, and SP |
| 2 Phase Rest | Restores 100% of maximum HP, MP, and SP |



All restoration values are calculated from maximum values unless explicitly stated otherwise.



### 2. Passive Non-Combat Recovery

While outside active combat resolution, characters naturally recover resources over time.

### Passive Recovery Rate

- Restores 10% of maximum HP, MP, and SP

This recovery applies only when:

- the character is not in active combat
- the character is not under a recovery-blocking effect
- the environment reasonably allows natural recovery

Passive recovery represents low-level stabilization, breathing recovery, mental restoration, and ambient mana equilibrium.



### 3. Daily Minimum Rest Requirement

All player characters must obtain at least **2 total phases of rest per day**.

Failure to meet this requirement may result in:

- exhaustion accumulation
- reduced recovery efficiency
- mental instability
- performance penalties
- other system-defined consequences

unless a valid skill, item, species trait, condition, or special effect explicitly overrides this rule.



### 4. Recovery Basis Rule

Unless explicitly stated otherwise:

- all percentage-based recovery is calculated from **maximum HP, MP, and SP**
- recovery is not based on current values

Example:

A character with:

- 100 Max HP
- 40 Current HP

recovering 25% HP restores:

- 25 HP<br>not:
- 10 HP



### 5. Recovery Stacking Rule

If multiple valid recovery effects apply during the same period:

- all valid recovery sources stack additively
- recovery effects combine unless a rule explicitly prevents stacking

This includes combinations from:

- resting
- regeneration skills
- consumables
- environmental effects
- healing structures
- passive abilities



### 6. Full Rest Rule

A completed **2-Phase Rest** is classified as a **Full Rest**.

A Full Rest restores:

- 100% HP
- 100% MP
- 100% SP

unless blocked, reduced, corrupted, or modified by another valid effect.

A Full Rest also satisfies the standard daily rest requirement.



### 7. Rest Tracking Rule

Whenever rest occurs, the system must explicitly record:

- rest duration
- recovery percentages applied
- exact HP restored
- exact MP restored
- exact SP restored
- active recovery modifiers
- whether the daily minimum rest requirement has been fulfilled

This tracking is mandatory for proper resource resolution and long-term condition management.



## ⚔️ COMBAT SYSTEM

### 1. Combat Types

#### Narrative Combat

Triggered when **Difficulty Ratio > 0.5**.

**Effect:**

●      Outcome is predetermined by superiority

●      Combat is resolved narratively

●      No detailed exchanges

**Still Track:**

●      HP

●      MP

●      SP

●      Resource consumption

**Use Cases:**

●      Trivial enemies

●      Clearly weaker opponents

●      Non-threatening encounters



#### Rules Combat

Triggered when outcome is **uncertain or contested**.

**Used for:**

●      Comparable enemies

●      Dangerous encounters

●      Tactical fights

●      Boss battles



### 2. Core Combat Model

#### Action–Reaction System

Combat is resolved through **Action vs Reaction**, not attack vs defense.

**Examples:**

●      Attack vs Dodge

●      Attack vs Block

●      Spell vs Interrupt

●      Movement vs Intercept

●      Escape vs Stop



#### Exchange System

Combat occurs in **Exchanges**:

1. Action declared
2. Reaction declared
3. Totals calculated
4. Outcome resolved
5. Effects applied

Multiple exchanges form a single encounter.



### 3. Initiative System

**Formula:**

Initiative = AGI + INT



**Rules:**

●      Highest initiative side acts first

●      Tie → simultaneous declaration

**Advantage of acting first:**

●      Controls opening move

●      Sets positioning

●      Enables setup



### 4. Action Economy

#### Major Action (Limit: 1 per battle exchange)

Examples:

●      Attack

●      Dodge / Block

●      Counter

●      Major spell

●      Terrain manipulation

●      Heavy movement

**Boss Exception:<br> **Bosses may exceed this limit.



#### Minor Actions (Unlimited, within reason)

Examples:

●      Positioning

●      Drawing weapons

●      Small support abilities

●      Observing

●      Assisting

●      Trap activation

●      Stance adjustment

**Rule:<br> **Minor actions cannot replace a major action.



### 5. Core Resolution Formula

#### Action / Reaction Value

Total Power = Relevant Stat + Modifiers + Skill/Spell + Curved d20 + combat approach



#### Multi-Stat Actions

If multiple stats apply:

Relevant Stat = Average of relevant stats



**Examples:**

●      Spell → (INT + WIS) / 2

●      Dodge → (AGI + INT) / 2

●      Attack → (AGI + STR) / 2

●      Block → (STR + END) / 2



#### combat Approach

Represents:

●      Planning

●      Method

●      Ingenuity

●      tactics

**Scaling:**

●      Tier 0 → 5–10

●      Tier 1 → 10–20

●      Tier 2 → 20–50

●      Tier 3 → 50–100

●      Tier 4 → 100–200

●      Tier 5 → 200–500

●      Tier 6 → 500+



#### Reaction Reference (NPC Baseline)

●      Tier 0 → 20–50

●      Tier 1 → 50–100

●      Tier 2 → 100–200

●      Tier 3 → 200–500

●      Tier 4 → 500–1000

●      Tier 5 → 1000–2000

●      Tier 6 → 2000+

*Note:* Reaction Reference can vary by domain (speed, defense, etc.).



#### Outcome Resolution

Outcome = Action Total − Reaction Total



●      Positive → Success

●      Negative → Failure

●      Margin → Strength of result



#### Effects

●      Damage = Outcome

●      Buff/Debuff = Outcome ÷ 5



### 6. Combat Loop

1. Declare Action
2. Declare Reaction
3. Calculate Totals
4. Compute Outcome
5. Apply Effects



### 7. Modifier Rule (Absolute)

Total Modifier = Sum of all relevant bonuses



No:

●      weighting

●      diminishing returns

●      hidden scaling

Only relevance determines inclusion.



### 7A. Combat Modifier-Sweep Transparency

For every meaningful combat Action or Reaction, list each included relevant modifier and why it applies. Also list any material available modifier that is excluded and why it does not apply. Combat uses its own Action-versus-Reaction process, but it may not use hidden bonuses, generic tier shortcuts, or unexplained modifier omissions.

### 8. Action Validity System (Critical)

#### Layer 1 — Validity Check

●      Can the action logically solve the problem?<br> → If NO → action fails immediately

#### Layer 2 — Numerical Resolution

●      If YES → apply formula



#### Domain Examples

**Invalid:**

●      Prediction vs unavoidable explosion → fails

**Valid:**

●      Prediction + movement vs linear attack → dodge possible

**Partial:**

●      Prediction vs multi-hit attack → reduced damage



#### Core Law

Capability determines if action works<br> Numbers determine how well it works

### 9. Combo Action

This is applicable when actions are combined together in sequence to boost combat action effect. A combo’s value is a **Relationship-Tier Combo**: it has no member cap and no longer uses the former Team Action Value formula.

#### Team Action Value Formula

<br> **Main** is the final attacker. Every other participant is a **sub**, and each sub contributes:

<br> boost(sub’s relationship tier with Main) × that sub’s own Action value

<br> Boosts **accumulate**: each successive attacker’s Action value includes every bonus before it. Contributions sum with no averaging, and the minimum contribution is +1 wherever the tier grants a nonzero percentage.

#### Boost Table

| Sub’s tier with Main | Tier name | Contribution |
| --- | --- | --- |
| −5 | Obsession (Destructive) | none |
| −4 | Hatred | none |
| −3 | Hostility | none |
| −2 | Rivalry | none |
| −1 | Tension | none |
| 0 | Neutral | +1% |
| +1 | Friendly | +2% |
| +2 | Trust | +5% |
| +3 | Deep Bond | +10% |
| +4 | Devotion | +20% |
| +5 | Absolute Bond | +50% |

#### Premises that must be met

Pre-conditions, checked before the combo begins:

- Actions must have the same target
- Actions must have the same intent, e.g. attack, defend, bind, or increase speed

Contact gate, checked per stage during the combo:

- Every stage’s Action value, including bonus already accumulated, must exceed the opponent’s Action value

#### Worked Example

Four attackers, each at Action value 30, all at Deep Bond (+10%) with Main:

- 1st: 30
- 2nd: 30 + 3 = 33
- 3rd: 30 + 3 + 3 = 36
- 4th (Main): 30 + 3 + 3 + 3 = 39

#### Failure Rule

- **Pre-condition failure** — different targets or different intents. The combo is **invalid**: it never began, nothing was committed to it, and the participants’ actions resolve separately as normal attacks.
- **Contact-gate failure** — a valid combo whose stage cannot beat the opponent’s Action value. The **combo collapses**: all accumulated damage and all bonuses are lost, and the participants still spend their phase and the resources they committed.
- The former member cap and per-member Action value minimum do not apply.
- Node-to-node tiers are recorded in `character relationship.md` under `## Node Relationship Tiers`.



### 10. Combat Rules Extensions

#### Multi-Target Attacks

●      One action

●      Separate resolution per target



#### Counter Mechanic

●      Counts as a **reaction**

●      Cannot be used if reaction is already spent



#### Reinforcement Rule

New enemies = **new encounter**

●      Major actions reset

●      Reactions reset

●      Initiative recalculated



#### Action Interruption

If a character is eliminated before acting:<br> → Action is lost



#### Trap System

●      Creation → Outside combat

●      Activation → Minor action



#### Environmental Manipulation

Can:

●      Force reactions

●      Apply penalties

●      Alter battlefield



#### Death Rule

HP = 0 → Death



No default:

●      unconscious states

●      death saves



### 11. Resource Tracking

Always track:

●      HP

●      MP

●      SP

Even in narrative combat.



### 12. Encounter Timing

●      1 Encounter = 0.5 Phase

●      2 Encounters = 1 Phase



#### Harvest Rule

Immediate post-combat harvesting:<br> → No extra phase (unless complex)



### 13. Boss Rules

Bosses may have:

●      Multiple major actions

●      Multiple reactions

●      Additional phases

●      Unique mechanics



## 🧪 NON-COMBAT SYSTEM

### 1. Action Sources

These actions are:

●      Crafting

●      Research

●      Engineering

●      Exploration

●      Training

●      Economy



### 2. Action System

#### Action value

A = Average Relevant Stats + Modifiers + d20 + Realistic Approach



#### Realistic Approach (Execution Quality)

Represents:

●      Planning

●      Method

●      Tools

●      Preparation

**Scaling:**

●      Tier 0 → 5–10

●      Tier 1 → 10–20

●      Tier 2 → 20–50

●      Tier 3 → 50–100

●      Tier 4 → 100–200

●      Tier 5 → 200–500

●      Tier 6 → 500+



### 2A. Resolution Assembly Protocol (Mandatory)

Every meaningful noncombat action, task, crafting attempt, business operation, training exercise, research experiment, or social contest must be assembled from the reality of its specific domain before it is resolved.

#### 1. Define the Domain and Method

State what is actually being attempted and how it is attempted: for example, batch craft, sale contract, field preservation, mana training, research experiment, or political negotiation.

#### 2. Select Relevant Stats

Use only the stat or multi-stat average that the method genuinely demands.

#### 3. Perform a Modifier Sweep

Check all possible sources, then include every modifier that genuinely helps the declared method:

- stat modifiers
- class modifiers and skills
- effect modifiers
- equipment and tools
- preparation, knowledge, injuries, allies, institutions, and other situational facts

The resolution must list included modifiers and why they apply. Important available modifiers that are excluded must also be listed with a reason.

#### 4. Build Task from World Reality

Task values are independent of the actor’s ECS and must reflect the actual requirement: market demand, institutional power, recipe complexity, batch scale, tool quality, material risk, social leverage, environmental conditions, and other valid facts.

#### 5. Apply Real-World Scaling

Interpret the completed Action or Task value through `Value ÷ 5` human-equivalent capability. The interpretation clarifies the fiction; it does not alter the mechanical value.

#### 6. Resolve Transparently

`Outcome = Action Value − Task Value`

No hidden bonus, generic tier shortcut, or automatic success may be added after the calculation.

#### ECS Boundary

ECS is the total of core stats. It represents broad build capacity and is used where an ECS rule explicitly calls for it, such as XP difficulty. ECS does not replace a domain-specific Action or Task value.

### 2B. Institutional Standing from Noncash Gains

Documented noncash gains may create **Institutional Standing** when a relevant outside group knows, recognizes, or can verify them. Examples include lawful recovery records, verified claimant returns, trade promises, custody credibility, repeat contracts, and recognized operational performance.

- Track each standing category as a **0–10 score** in the Ledger.
- A standing score grants one relevant modifier: 0–2 = +0; 3–5 = +1; 6–8 = +2; 9–10 = +3.
- Standing applies only to a fitting domain and counterpart, such as Trade Standing in merchant negotiations or Adventurer-Recovery Standing in bounty, recovery, route-security, and adventurer-material exchange work.
- A documented item may establish evidence for standing, but its value cannot be counted again as a separate generic modifier in the same resolution. Use either the category modifier or a distinct, non-overlapping factual effect.
- Standing is not automatic social control, does not affect unrelated combat or crafting, and can fall when the underlying credibility is disproved, ignored, or damaged.
- New records increase standing only when their recognition is validly established; merely possessing an unsubmitted packet does not automatically increase the score.

### 2C. Outcome-Based Practice Carryover and Derived Refinement

Repeated, logged, meaningful practice with the **same narrow method** changes both preparation and real difficulty through the last eligible attempt’s outcome margin.

For a consecutive chain of directly comparable attempts, track cumulative **Practice Carryover `P`**.

- The first eligible follow-up after a documented attempt below raw +10 begins at `P = 1`.
- Every further directly comparable attempt that continues the same narrow method increases the chain by one: `P_next = P_current + 1`.
- Apply `+P` to the new pre-assistance Action and `-P` to the new Task. When cognitive assistance is valid, the Action carryover is included before the relevant percentage support is applied.
- A changed method, material, pressure, environment, goal, support condition, or task scope breaks the chain unless the record explains why the prior practice genuinely transfers.
- A documented uncapped raw result of **+10 or higher** ends the carryover chain. The decisive result becomes evidence toward stable competence, certification, or a permanent modifier instead.

A prior session counts only if it involved a real attempt at the same method under meaningful conditions. Trivial repetition, unrelated work, or a different material/problem does not count. A changed environment, pressure type, material, or independent field condition may reduce or remove carryover where the old practice does not transfer.

Practice Carryover is a displayed situational factor, not a permanent modifier. It cannot be double-counted with an earned modifier that already represents the same mastered method, and it must never replace the threshold for earning a permanent modifier, certification, or breakthrough.

#### Derived Refinement, Branching, and Combined Lineage

A character may refine a documented technique into a **new but related** technique only when each claimed predecessor has a recorded decisive **uncapped raw outcome of +10 or higher**. This is easier than inventing an unrelated modifier only when the experiment record explains the shared method, material, body pattern, mana logic, or operational domain.

- A certification or earned modifier alone does not qualify a predecessor for Derived Refinement; its experiment record must contain the required +10-or-higher raw outcome.
- A qualifying derived technique may itself become a predecessor for a later, narrower technique after it earns its own qualifying raw +10 outcome. Progression may therefore branch as a tree rather than tracing only to one original method.
- A new technique may combine multiple qualifying predecessors when each supplies a distinct, necessary component. For example, spell-control understanding can supply the automation and mana-structure component while alchemical understanding supplies the reaction, ingredient, and process-control component of an automated alchemy spell.
- Apply every relevant existing named modifier normally.
- For each genuinely relevant, non-overlapping predecessor, calculate `L_i = min(3, floor(qualifying predecessor raw margin ÷ 10))`. Add all distinct `L_i` values to Action and subtract their total from Task. Do not count two predecessors for the same underlying knowledge or method.
- The experiment record must name every predecessor, its qualifying raw margin, the distinct component it contributes, and the boundary where it stops transferring. A new material, pressure type, environment, or goal may reduce or remove that predecessor’s L.
- Do not add Lineage Familiarity when an existing modifier already directly covers the entire attempted method; that would double-count mastery.
- Derived Refinement only changes the starting difficulty and approach. It does not bypass repeated-success, experimentation, certification, or breakthrough requirements for the new modifier.

### 2D. Facility Modifier Bands

A functioning facility may grant a location-bound modifier when its tools, layout, storage, safety, staff support, or controlled conditions materially aid the declared action. A facility does not grant a generic bonus outside its documented scope.

- **Tier 1 facility:** +2 to +5, selected from its actual specialization, completeness, and operating quality.
  - +2: basic licensed, limited, or lightly equipped site.
  - +3: capable staffed or properly equipped site.
  - +4: specialized and well-maintained site with meaningful control.
  - +5: dedicated, fully functional specialist production or training site.
- Facility modifiers apply only while the actor uses the facility for its documented function. They may combine with distinct personal modifiers, but never with a superseded lower-tier version of the same facility.
- Every active facility and exact modifier must appear in the Ledger’s Facility Modifier Index.

### 2E. Distinct Cognitive-Assistance Modifiers

A stored-knowledge system and an analytical guide are distinct supports, like learning from a book and learning from a teacher. They may both apply to one valid intellectual action when each independently contributes; one does not replace or invalidate the other.

- **Knowledge Database Rune:** +10% to the pre-assistance Action Value when it retrieves relevant stored knowledge, records, examples, or validated reference material that is actually used in the method.
- **Ava / Analyst Mirror:** +10% to the pre-assistance Action Value when Ava meets her stated valid-assistance requirements and her analysis is actually used.
- **Combined Cognitive Assistance:** when both supports validly contribute to the same action, add a further +5% to the same pre-assistance Action Value for retrieval-and-interpretation synergy.
- Apply these percentages additively, not multiplicatively: when all three apply, `Final Action = Pre-Assistance Action × 1.25`.
- The integrated system makes both supports concurrently available. It does not make either support universal: each must have relevant information, sufficient time, and a real role in a valid intellectual, analytical, structural, strategic, or knowledge-based method.
- These support modifiers do not apply to raw physical action, reflex action, charisma-only persuasion, unsupported crafting labor, invalid action, or any task outside the supports’ actual knowledge and analytical scope.

### 2F. Routine Validated Production

Once a production or crafting method is **validated** — proven recipe set, proven matching materials, the required facility and its bonus, any relevant batch template, and a scale the actor has already completed — repeating it at or below that proven scale is **routine validated production** and does not require a roll. It may still be recorded for bookkeeping.

A roll is required again when circumstance changes materially:

- a new or altered recipe
- a new, unfamiliar, or substituted material
- a larger scale than the actor has previously completed
- a damaged, absent, or unavailable facility or template
- a hostile, contested, or unreliable setting
- a condition that genuinely interferes with the work

This rule prevents invented difficulty on work a character has repeatedly and reliably completed. It does not grant automatic success on first attempts, on changed methods, or on work whose inputs or conditions have changed.

### 3. Task System

#### Task Value

Task = Difficulty + Novelty + applicable Integration / Independence / Field-Risk factors

Each additional factor must be real, stated, and non-overlapping. Do not add a factor merely because an actor is strong or to force failure.



#### Difficulty Scaling

●      Tier 0 → 20–50

●      Tier 1 → 50–100

●      Tier 2 → 100–200

●      Tier 3 → 200–500

●      Tier 4 → 500–1000

●      Tier 5 → 1000–2000

●      Tier 6 → 2000+



#### Novelty Scaling

●      Tier 0 → 10–20

●      Tier 1 → 20–50

●      Tier 2 → 50–100

●      Tier 3 → 100–200

●      Tier 4 → 200–500

●      Tier 5 → 500–1000

●      Tier 6 → 1000+

#### Integration / Independence / Field-Risk Factors

Use only factors actually present in the declared work.

- **Integration:** +5–10 for a minor interaction between known methods; +15–30 for two genuinely interdependent domains; +30–60 for a novel system whose parts must operate together, such as autonomous spell-and-alchemy process control.
- **Independence:** +0 under direct mentor correction in a controlled setting; +10–20 for independently verified work; +20–40 for independent field work, variable conditions, or no-correction evaluation.
- **Field Risk:** +0 when a failed attempt is safely reversible; +5–15 when it risks scarce materials, a paid contract, or meaningful loss; +15–40 when it risks injury, hazardous release, major property damage, or irreversible loss.

These factors describe the world requirement, not the actor. If one factor already represents the same complication as Difficulty or Novelty, do not count it again.

### 3A. Permanent Advancement Task Floors

These are starting floors for future attempts to create a permanent capability; actual documented complexity may require a higher Task. They do not retcon already earned modifiers.

- **New independent Tier 1 modifier:** normally Task **100–130**, including real novelty and independent or variable-condition proof.
- **Derived Tier 1 modifier:** establish the Task from the same 100–130 starting range, then apply only valid Lineage Familiarity reductions. It is easier than unrelated invention, not automatic.
- **Multi-domain permanent technique or modifier:** normally Task **120–160+** before valid lineage reductions, plus any real integration, independence, and field-risk factors.
- **Tier 2 breakthrough or permanent Tier 2 capability:** use the Tier 2 difficulty and novelty ranges together, normally at least **150–300** before any valid reductions, and require an appropriate personal framework, proof, and advancement structure.

### 4. Outcome Resolution

Outcome = Action value − Task



**Cap:** +10



#### Outcome Results

●      < -5 → Great Failure

●      -5 to -3 → Failure

●      -3 to 0 → Partial Failure

●      0 to 3 → Partial Success

●      3 to 5 → Success

●      5 → Great Success



#### Failure Consequences

●      Great Failure → destruction / injury / death

●      Failure → loss of materials

●      Partial Failure → flawed output + learning



### 5. Action Time

- basic → within Phase
- Simple → 1 Phase
- Advanced → Multiple Phases
- Major → Days



### 6. Collaborative Action

#### Team Action value Formula

<br> Main is the **lead character**. Every other participant is a **sub**, and each sub contributes:

<br> boost(sub’s relationship tier with Main) × that sub’s own Action value

<br> Team Action value = Main’s Action value + Σ (sub contributions)

<br> Boosts apply **once** in noncombat rather than accumulating. The minimum contribution is +1 wherever the tier grants a nonzero percentage. The combat contact gate does not apply outside combat. The boost table is in `### 9. Combo Action`.



#### Behavior

●      Strongest member defines baseline

●      Team adds proportional amplification

●      Weak members contribute less

●      Strong members scale output significantly



### ⚙️ SYSTEM SUMMARY

This system ensures:

●      No ambiguity → everything resolves numerically

●      No hidden scaling → full transparency

●      Skill expression → via action validity

●      Balance → through domain constraints, not artificial limits



## Consumable Growth and Reward System

### Overview

Food, pills, potions, herbs, and edible harvest substances can grant:

- XP
- Temporary Modifiers
- Effect Modifiers

Rewards are determined by:

- Consumable tier
- Material quality
- Production difficulty
- Creator skill
- Character tier



### Core Rules

#### Tier Restrictions

A character cannot gain **any effect** from consumables below their own tier.

However:

- XP rewards are repeatable
- Temporary modifiers are repeatable
- Characters may gain XP and temporary modifiers from consumables above their tier

##### Example

A Tier 0 character consuming Tier 4 food may still gain:

- the XP reward
- the temporary modifier

but may not safely integrate permanent effects beyond their capability.



#### Material Consistency

For food, pills and potions:

- the materials used must match the tier of the final product
- higher-tier products cannot be created from lower-tier materials alone



#### Effect Modifier Restrictions

Effect modifiers are tightly controlled.

##### Same-Material Rule

A character may only gain a permanent effect modifier once from:

- the same meal
- the same herb
- the same edible harvest substance
- the same potion
- or products created from the same core materials

This prevents permanent stat farming through repeated consumption.



#### Permanent Effect Modifier Requirements

Permanent effect modifiers require all of the following:

- minimum Tier 3 item quality
- meaningful biological or magical integration
- sufficient potency to justify lasting character change

Additional requirements:

##### Food

Permanent food effects require:

- a chef of equal or higher tier than the consumable

##### pills and potions

Permanent alchemical effects require:

- an alchemist of equal or higher tier than the consumable



### Food Rewards



| **Tier** | **Rewards** |
| --- | --- |
| Base | No reward |
| Tier 0 | 1–5 XP |
| Tier 1 | 5–20 XP, temporary modifier of +1 to +2 for 1 phase |
| Tier 2 | 20–100 XP, temporary modifier of +2 to +5 for 1 day |
| Tier 3 | 100–500 XP, temporary modifier of +5 to +10 for 1 day, Tier 2 effect modifier |
| Tier 4 | 500–2000 XP, temporary modifier of +10 to +20 for 1 day, Tier 3 effect modifier |
| Tier 5 | 2000–5000 XP, temporary modifier of +20 to +50 for 1 day, Tier 4 effect modifier |
| Tier 6 | 5000–20000 XP, temporary modifier of +50 to +100 for 1 day, Tier 5 effect modifier |



### Pills and Potions Rewards



| **Tier** | **Rewards** |
| --- | --- |
| Tier 0 | 10–50 XP |
| Tier 1 | 50–200 XP, temporary modifier of +1 to +2 for 1 phase |
| Tier 2 | 200–1000 XP, temporary modifier of +2 to +5 for 1 day |
| Tier 3 | 1000–5000 XP, temporary modifier of +5 to +10 for 1 day, Tier 2 effect modifier |
| Tier 4 | 5000–20000 XP, temporary modifier of +10 to +20 for 1 day, Tier 3 effect modifier |
| Tier 5 | 20000–50000 XP, temporary modifier of +20 to +50 for 1 day, Tier 4 effect modifier |
| Tier 6 | 50000–200000 XP, temporary modifier of +50 to +100 for 1 day, Tier 5 effect modifier |



### Herb and Edible Harvest Rewards



| **Tier** | **Rewards** |
| --- | --- |
| Tier 0 | 1–5 XP |
| Tier 1 | 5–20 XP |
| Tier 2 | 20–100 XP, temporary modifier of +1 to +2 for 1 phase |
| Tier 3 | 100–500 XP, temporary modifier of +2 to +5 for 1 day |
| Tier 4 | 500–2000 XP, temporary modifier of +5 to +10 for 1 day, Tier 3 effect modifier |
| Tier 5 | 2000–5000 XP, temporary modifier of +10 to +20 for 1 day, Tier 4 effect modifier |
| Tier 6 | 5000–20000 XP, temporary modifier of +20 to +50 for 1 day, Tier 5 effect modifier |



### Specialized Consumables

Not all consumables are designed for XP gain.

Some herbs, foods, and alchemical products instead provide direct functional effects such as:

- healing
- detoxification
- hallucinations
- poison
- regeneration
- stamina restoration
- mana restoration
- sensory enhancement
- sleep induction
- emotional suppression

In these cases, the consumable grants its primary effect instead of XP.

#### Example

A Tier 0 healing potion restores:

- 10–50 HP

rather than granting XP.



### Design Logic

This system exists because:

- higher-tier consumables are difficult to acquire
- higher-tier food requires multiple materials and skilled preparation
- higher-tier pills and potions requires specialized knowledge and refinement
- raw herbs and harvest substances are easier to obtain than refined products
- permanent modifiers should feel meaningful, rare, and earned



### Balance Notes

#### Food

Food may grant greater rewards than raw herbs because it combines:

- multiple ingredients
- preparation techniques
- creator skill



### pills and potions

pills and potions grants the highest rewards because it is:

- highly refined
- specialized
- resource intensive
- heavily tier-gated



### Permanent Effects

Permanent effect modifiers:

- begin at Tier 3
- are intentionally rare
- are not meant to be farmed repeatedly



### Repeatability Rules

#### Repeatable

The following may be repeatedly gained:

- XP
- temporary modifiers

No hard repeat limit exists unless specifically stated by an item.

### Crafting Output Rules

#### Potions

- **Great Success:** 3 potions
- **Success:** 2 potions
- **Partial Success:** 1 potion

#### Pills

- **Great Success:** 5 pills
- **Success:** 3 pills
- **Partial Success:** 1 pills

#### Note

Pills produce a higher quantity than potions because they are weaker and less effective per unit.



### Restricted

Permanent effect modifiers are restricted by:

- the same-material rule
- creator tier requirements
- minimum item tier requirements
- meaningful integration conditions

They are not freely repeatable.


## STAT SYSTEM
### 🧬 CORE STAT SYSTEM



#### 1. STRENGTH (STR)

**Definition:<br> **Raw physical force applied to the world.

**Governs:**

●      Melee damage

●      Lifting, pushing, breaking

●      Grappling

●      Brute-force actions

**Effects:**

●      Increases physical damage

●      Increases Stamina

●      Improves carry capacity

**Penalty (STR < 3):**

●      −1 to all force-based actions

●      Reduced carry capacity

●      Rapid fatigue



#### 2. AGILITY (AGI)

**Definition:<br> **Speed, reflex, coordination, and precision.

**Governs:**

●      Dodging

●      Stealth movement

●      Finesse attacks

●      Precision tasks

●      Acrobatics

**Effects:**

●      Increases Defense

●      Increases Initiative

●      Enables advanced evasion

**Penalty (AGI < 3):**

●      −1 to defense rolls

●      Noisy movement

●      Poor coordination



#### 3. ENDURANCE (END)

**Definition:<br> **Physical resilience and sustained capability.

**Governs:**

●      HP pool

●      Stamina

●      Survival

●      Resistance

●      Long-duration tasks

**Effects:**

●      HP = END × 5

●      Reduces fatigue

●      Improves environmental resistance

**Penalty (END < 3):**

●      Constant fatigue

●      Slow recovery

●      High injury risk



#### 4. INTELLIGENCE (INT)

**Definition:<br> **Logic, analysis, and structured thinking.

**Governs:**

●      Spell damage

●      Spell complexity

●      Crafting

●      Analysis

●      Investigation

**Effects:**

●      Increases spell power

●      Unlocks higher-tier abilities

●      Improves crafting and ritual efficiency

**Penalty (INT < 3):**

●      Unstable spellcasting

●      Increased failure rates

●      Poor analytical capability



#### 5. WISDOM (WIS)

**Definition:<br> **Mana control, intuition, and awareness.

**Governs:**

●      Mana pool

●      Mana recovery

●      Concentration

●      Insight

●      Spiritual perception

**Effects:**

●      MP = WIS × 5

●      Extends spell duration

●      Increases resistance to mental effects

●      Improves healing and recovery

**Penalty (WIS < 3):**

●      Low mana capacity

●      Weak concentration

●      Poor intuition



#### 6. PRESENCE (PRE)

**Definition:<br> **Influence exerted through aura and identity.

**Governs:**

●      Social interaction

●      Intimidation

●      Leadership

●      Aura-based stealth

●      Spiritual pressure

**Effects:**

●      Enables aura-based combat

●      Improves crowd control

●      Enhances charm and fear effects

**Penalty (PRE < 3):**

●      −1 to social rolls

●      Weak aura

●      Easier detection



### ⚙️ DERIVED STATS

Calculated directly from core stats:

●      **HP** = END × 5

●      **MP** = WIS × 5

●      **Stamina** = STR + END

●      **Initiative** = AGI + INT

●      **Carry Load** = STR × 10

#### Resistances

●      Physical = END

●      Magical = INT + WIS

●      Mental = WIS

●      Social = PRE



## 🧩 MODIFIER SYSTEM

### Core Principle

Modifiers define **performance beyond base stats**.

**Sources:**

●      Stats

●      Class

●      Effects

●      Equipment

●      Situation



### 1. Stat Modifiers

**Rules:**

●      Only relevant stats apply

●      Multiple stats can combine

**Examples:**

●      STR + AGI → physical attacks

●      INT + WIS → magic

●      STR + END → defense



#### 1. Major vs Minor Stats

Each build defines:

●      **2 Major Stats** → primary focus

●      **4 Minor Stats** → secondary support

**Examples:**

●      Mage → INT, WIS

●      Fighter → STR, AGI

●      Tank → STR, END



#### 2. Modifier Distribution by Tier



| **Tier** | **Major Mods** | **Minor Mods** |
| --- | --- | --- |
| 0 | 2 | 1 |
| 1 | 3 | 2 |
| 2 | 4 | 3 |
| 3 | 5 | 4 |
| 4 | 6 | 5 |
| 5 | 7 | 6 |



#### 3. Conversion Rule

●      2 Minor = 1 Major

●      Minor stats can be promoted to Major roles

note: 2 and 3 are just to help you build enemies it isn't a universal rule what is the true rule is 4

#### 4. Modifier Count Scaling

Based on stat value:

●      5 → 1 modifier

●      10 → 2

●      20 → 3

●      50 → 4

●      100 → 5

●      200 → 6

●      500 → 7

●      1000 → 8

#### Examples

END SKILL

Hard bone

Boost + 20 to:

·       defence

·       body strength



### Class Modifiers

●      Granted through class progression

●      Scale with tier

●      Represent specialization



#### Examples

Swift blade

Boost + 4 to:

·       Blade attacks

·       Blade speed

·       Blade movements



### Effect Modifier

Effect modifiers are earned when repeated meaningful action, experimentation, breakthrough behavior, or specialized performance creates a stable and reusable improvement in how a character functions.

They are not granted automatically by time, level, or tier.<br>They must be justified by action history.

#### 1. Sources of New Effect Modifiers

A new effect modifier may be gained from:

- repeated successful use
- experimentation success
- training breakthrough
- combat adaptation
- noncombat specialization
- behavior repeatedly proven under pressure
- Consumption of things

#### 2. Threshold

A new effect modifier may only be gained through one of the following:

- repeated meaningful success
- a major breakthrough event
- successful creation through the experimentation system

Meaning:

- one lucky action is not enough
- one trivial repetition is not enough
- the gain must represent stable capability, not temporary performance

#### 3. Strength

New effect modifiers must obey the existing tier strength ranges.

Example:

- Tier 0 effect modifier: **+1 to +2**
- Tier 1 effect modifier: **+2 to +5**

This prevents effect modifiers from breaking the existing modifier system.

#### 4. Anti-Abuse Rules

Effect modifiers cannot be farmed freely.

##### Hard limits

- no duplicate effect modifier from the same behavior
- no trivial farming
- modifier must represent a stable change in capability
- modifier must be justified by action history
- modifier must have a clear domain of relevance
- if the behavior is too broad, the modifier must be narrowed before being granted

That last part is important because otherwise people will try to gain vague things like:

- “good fighter”
- “smart planner”

Instead of specific effects like:

- wolf-pattern chaining
- relay-space stabilization
- controlled battlefield baiting

#### 5. Upgrade Rule

Effect modifiers do not automatically grow with the character.

A character becoming stronger, leveling up, or advancing tier does not automatically upgrade existing effect modifiers.

To improve an effect modifier, the character must actively integrate and refine it through use, experimentation, training, or breakthrough.

That means:

- effect modifiers are not passive scaling rewards
- they are living techniques or patterns that must be developed
- a Tier 0 modifier can remain Tier 0 forever if never upgraded
- upgrading it requires actual in-world effort



#### 6. Modifier Identity Rule

Every new effect modifier must have:

- a name
- a tier
- a short description
- a clear boost domain

Example:<br>**Wolf Pattern<br>**Tier: 0<br>Boost: +2 to chained dual-blade attacks, unrelenting attack flow, pressure through continuous offense



### Equipment Modifiers

●      Provided by items

●      Scale with item tier

●      May:

○      boost stats

○      unlock abilities

#### Examples

Assassin cloak

Boost + 2 to:

·       hidden

·       ambush attack

·       stealth



### Situational Modifiers

**Not tier-based**

Depend on context:

●      Terrain

●      Preparation

●      Ambush

●      Knowledge

●      Lighting



### Modifier Behavior Rules

●      Only relevant modifiers apply

●      Some modifiers unlock mechanics (not just numbers)

●      Alignment increases effectiveness

●      Modifiers define build identity

![*](assets/game-rules-1/image1.png)

#### Modifier Strength by Tier

Applies to all non-situational modifiers:

●      Tier 0 → +1 to +2

●      Tier 1 → +2 to +5

●      Tier 2 → +5 to +10

●      Tier 3 → +10 to +20

●      Tier 4 → +20 to +50

●      Tier 5 → +50 to +100



### ⚠️ SCALING REALITY

At higher tiers:

●      Modifier stacking grows exponentially

●      Without constraints → system breaks

**Control comes from:**

●      Action validity

●      Domain limits

●      Counterplay



## 🔥 ACTIVE SKILL SYSTEM

### 1. Tier Determination

A skill’s tier is defined by the **highest of:**

●      Power output

●      Area of effect

●      Conceptual complexity

●      Energy cost



### 2. Skill Tiers

#### Tier 0 — Human Level

●      Small effects

●      Single target

●      Low cost

**Effect:** +10 to +15<br> **Cost:**

●      2–10 MP

●      2–10 SP



#### Tier 1 — Superhuman

●      Enhanced force

●      Moderate impact

**Effect:** +20 to +45<br> **Cost:**

●      10–20 MP

●      10–20 SP



#### Tier 2 — Village Level

●      Wide AoE

●      High impact

**Effect:** +50 to +95<br> **Cost:**

●      20–50 MP

●      20–50 SP



#### Tier 3 — City Level

●      Massive scale

●      War-impacting

**Effect:** +100 to +190

**Cost:**

●      50–100 MP

●      50–100 SP



#### Tier 4 — National Level

●      Alters regions

**Effect:** +200 to +480

**Cost:**

●      100–200 MP

●      100–200 SP



#### Tier 5 — Continental Level

●      Reshapes landmass

**Effect:** +500 to +990

**Cost:**

●      200–500 MP

●      200–500 SP



#### Tier 6 — World Level

●      Extreme, non-mortal

**Effect:** 1000+

**Cost:**

●      500+ MP

●      500+ SP



### 3. Skill Creation

Uses the **Experimentation System**:

●      Action value (stats + modifiers + knowledge + approach)<br> vs

●      Task (difficulty + novelty)

Success → skill created



### 4. Skill Evolution

Skills evolve through:

●      Practice

●      Experimentation

●      Combination

●      Improved control

**Example Path:<br> **Mana Missile → Mana Constructs → Telekinetic Weapons



### 5. Skill Categories

Used for Action value relevance and interaction logic:

●      Combat

●      Movement

●      Support

●      Crafting

●      Infrastructure

●      Economic



### ⚙️ FINAL SYSTEM INTENT

This system works because:

●      Stats define **capability domains**

●      Modifiers define **execution strength**

●      Skills define **application**

●      Action validity prevents abuse

●      Scaling is powerful but not unchecked



## IV. DUAL XP SYSTEM — THE TWO PATHS OF GROWTH

Growth flows through **two separate XP systems**, each governing a different kind of advancement:

●      **Normal XP** → life, struggle, survival, and overall evolution

●      **Class XP** → mastery, discipline, specialization, and role refinement

These two systems are **never interchangeable**.<br> They are earned differently, grow independently, and reward different forms of progress.



### 1. NORMAL XP SYSTEM — LIFE XP

Normal XP represents **broad personal growth** gained through hardship, achievement, and meaningful action.

#### A. How Normal XP Is Earned

Normal XP is gained from actions that meaningfully advance the character’s life, survival, or development.

Examples:

●      defeating enemies

●      surviving dangerous conditions

●      completing quests

●      exploring unknown territory

●      pushing physical or mental limits

●      training body or mind

●      crafting difficult items

●      solving meaningful challenges

**Core Rule:<br> **If the world would consider the action significant, it may grant Normal XP.



#### B. Nature of Normal XP

Normal XP reflects **overall character evolution**, not specialization.

It tracks:

●      survival

●      struggle

●      adaptation

●      discovery

●      achievement



#### C. Level Cap

Normal XP has **no level cap**.

Characters can continue leveling indefinitely.<br> Growth is theoretically infinite.



#### D. Normal Level-Up Rewards

Each Normal Level grants:

+15 Stat Points

These points may be distributed freely across the six core stats.




### 2. CLASS XP SYSTEM — MASTERY XP

Class XP represents **focused growth within a chosen role**.

It is narrower than Normal XP, but more specialized.



#### A. How Class XP Is Earned

Class XP is earned only through **class-aligned actions** that are:

●      unique

●      purposeful

●      tied to the class identity

Examples:

●      a warrior developing a new stance

●      a mage performing a new ritual

●      a rogue infiltrating a new type of location

●      a cleric executing a profound healing

●      a ranger taming a new species

**Core Rule:<br> **Class XP is awarded only when the action deepens mastery of the class itself.



#### B. Nature of Class XP

Class XP reflects:

●      specialization

●      discipline

●      technical refinement

●      mastery of role

●      advancement within class identity



#### C. Level Cap

Class XP also has **no level cap**.

Class progression can continue indefinitely, unlocking:

●      new class modifier


#### D. Class Level-Up Rewards

Class Level-Ups do **not** grant stat points.

Instead, they grant class-based advancement such as:

●      stances

●      forms

●      passive features

●      transformations

●      class abilities

**Class Level-Up = mastery evolution**



### 3. CORE DISTINCTION

#### Normal XP gives

●      broader growth

●      stat increases

●      overall scaling

●      universal evolution

#### Class XP gives

●      narrower growth

●      class depth

●      technical refinement

●      specialization rewards



### 4. BASE XP

Each challenge or opponent has a **Base XP value** determined by:

●      rarity

●      ecological danger

●      combat role

●      overall significance

#### Base NORMAL XP by Tier

●      **Tier 0** → 100 to 200

●      **Tier 1** →  200 to 500

●      **Tier 2** → 500 to 1000

●      **Tier 3** → 1000 to 2000

●      **Tier 4** → 2000 to 5000

●      **Tier 5** → 5000 to 10000

Base XP is the starting reward **before difficulty adjustment**.



#### Base CLASS XP by Tier

●      **Tier 0** → 50 to 100

●      **Tier 1** →  100 to 200

●      **Tier 2** → 200 to 500

●      **Tier 3** → 500 to 1000

●      **Tier 4** → 1000 to 2000

●      **Tier 5** → 2000 to 5000



Base XP is the starting reward **before difficulty adjustment**.



### 5. DIFFICULTY RATIO

Difficulty Ratio determines how meaningful the challenge was, and therefore how much XP should be awarded.



#### A. Combat Difficulty Ratio

For combat:

Player ECS = total player stats

Enemy ECS = total enemy stats

D = 1 + (Enemy ECS − Player ECS) / (15 + Player Tier × 5)



##### Interpretation

●      If enemy power is close to player power, D stays near 1

●      If enemy power is much higher, D rises above 1

●      If enemy power is far lower, D drops below 1

This makes XP scale by relative challenge, not just enemy tier.



#### B. Non-Combat Difficulty Ratio

For non-combat tasks:

D = Task / Player ECS



This compares task difficulty directly against the character’s effective capability.



### 6. NON-COMBAT OUTCOME BANDS

Non-combat results are determined by comparing the task to the player’s ECS.

Using your structure, the clean version is:

●      **Great Success** → D × 2

●      **Success** → D × 1.5

●      **Partial Success** → D × 1

●      **Partial Failure** → D × 0.75

●      **Failure** → D × 0.5

●      **Great Failure** → D × 0.25

This should be read as an **XP multiplier modifier based on result quality**, not as the difficulty formula itself.

So the actual structure becomes:

Base Non-Combat Difficulty = Task / Player ECS

Final XP Multiplier = Difficulty Ratio × Outcome Modifier



That makes the system much cleaner.



### 7. XP REWARD FORMULA

#### Standard Formula

XP Reward = Base XP × D



Where:

●      **Base XP** = the intrinsic value of the challenge

●      **D** = adjusted difficulty multiplier

For non-combat tasks, if using outcome bands:

XP Reward = Base XP × D × Outcome Modifier



### 8. MINIMUM XP RULE

If D < 0.3 → no XP



This prevents farming trivial actions or weak enemies for infinite growth.

**Meaning:<br> **If the challenge was too easy to matter, it grants no advancement.



### 9. XP REQUIRED TO LEVEL — NORMAL XP

The XP required for the next Normal Level is:

Normal XP Required = 500(Level)(Tier + 1)



Cleaner written form:

Normal XP Required = 500 × (Level) × (Tier + 1)



#### Behavior

●      scales with current level

●      scales harder at higher tiers

●      keeps infinite growth possible while slowing progression naturally



### 10. XP REQUIRED TO LEVEL — CLASS XP

The XP required for the next Class Level is:

Class XP Required = 100(Level)(Tier + 2)



Cleaner written form:

Class XP Required = 100 × (Level) × (Tier + 2)



#### Behavior

●      cheaper than Normal leveling

●      supports more frequent mastery progression

●      keeps class growth active without overshadowing stat growth



### 11. FINAL SYSTEM LOGIC

#### Normal XP

Represents:

●      life experience

●      broad evolution

●      survival-based growth

Rewards:

●      +15 stat points per level



#### Class XP

Represents:

●      role mastery

●      specialization

●      technical refinement

Rewards:

●      modifiers



#### Shared Rules

●      both scale infinitely

●      both use challenge relevance

●      both reject trivial farming

●      both reward meaningful progression, but in different ways



### 12. CLEAN SYSTEM SUMMARY

#### Normal XP

●      broad growth

●      stat advancement

●      survival and achievement based

##### Class XP

●      specialized growth

●      mastery advancement

●      class identity based

##### XP Formula

XP = Base XP × Difficulty Multiplier



##### Non-Combat Version

XP = Base XP × Difficulty Multiplier × Outcome Modifier



##### No XP Threshold

If D < 0.3 → no XP



##### Level-Up Formulas

Normal XP Required = 500 × (Level − 1) × (Tier + 1)

Class XP Required = 100 × (Level − 1) × (Tier + 2)



## V. CANONICAL TIER SYSTEM

### 1. Tier–Level Structure

Tiers define **power brackets**, not just levels.

●      **Tier 0** → Level 1–2

●      **Tier 1** → Level 3–5

●      **Tier 2** → Level 6–10

●      **Tier 3** → Level 11–20

●      **Tier 4** → Level 21–50

●      **Tier 5** → Level 51–100

●      **Tier 6** → Level 100+

**Key Principle:<br> **Levels increase **stats**.<br> Tiers define **what those stats can actually do**.



### 2. Stat Growth System

All characters and monsters follow:

Total Stats = a + 15 × (Level − 1)



Where:

●      **a** = starting stat pool (25–35 typical, up to ~40 for monsters)

#### Properties

●      Linear growth → predictable scaling

●      +15 stats per level → aligns with your Normal XP system

●      Supports clean Action value calculation



### 3. Nature of Tiers

Tiers are **qualitative thresholds**, not just numeric ones.

●      Levels → increase power steadily

●      Tiers → unlock new **categories of impact**



### 4. Tier Power Scale

#### Tier 0 — Human Level

●      Peak human capability

●      Skilled fighters, hunters, basic mages

●      No true supernatural dominance



#### Tier 1 — Superhuman

●      Enhanced speed and strength

●      Combat superiority

●      Dominates small engagements



#### Tier 2 — Village Level

●      Area destruction

●      Battlefield control

●      Environmental impact begins



#### Tier 3 — City Level

●      Large-scale devastation

●      War-level influence

●      Strategic threat



#### Tier 4 — Country Level

●      National-scale destruction

●      Ecosystem disruption

●      Large-region control



#### Tier 5 — Continental Level

●      Climate and terrain manipulation

●      Massive-scale phenomena

●      World-impacting events



#### Tier 6 — World Level

●      Beyond mortal systems

●      Requires separate mechanics

●      Not bound by standard rules



### 5. Tier Breakthrough Rule (Critical)

**Levels alone do NOT advance tiers.**

To reach a new tier, a character must:

Successfully create a skill of the next tier



#### Example

●      Tier 0 → Tier 1 → requires Tier 1 skill creation

●      Tier 1 → Tier 2 → requires Tier 2 skill creation



#### Implications

Tier advancement depends on:

●      experimentation

●      knowledge

●      creativity

●      execution

●      risk

**Result:<br> **Progression is **earned through innovation**, not grinding.



### 6. Breakthrough Difficulty Scaling

Each tier jump is exponentially harder:

●      Human → Superhuman → difficult

●      Superhuman → Village → extremely difficult

●      Village → City → rare

●      Higher tiers → increasingly near-impossible

Because each tier represents a **new paradigm**, not just higher numbers.



### 7. Gameplay Structure

This creates a dual progression system:

●      **Levels → steady stat growth**

●      **Tiers → breakthrough-based power evolution**



### 8. Tier Interaction in Combat

For each tier difference:

+10 to Actions

+10 to Reactions



#### Meaning

●      Higher-tier combatants have inherent advantage

●      Lower-tier fighters are still viable with:

○      strategy

○      preparation

○      teamwork

○      domain advantage



### 9. Tier Utilization Rule

Characters cannot fully use **higher-tier tools or abilities**.

#### Effects of mismatch

●      instability

●      reduced output

●      backlash

●      incomplete activation



### 10. Equipment Scaling Rule

Lower-tier equipment degrades under higher-tier usage.

#### Possible outcomes

●      reduced effectiveness

●      durability failure

●      structural breakage

**Example:<br> **A Tier 0 weapon used by a Tier 3 character may break under force output.



## VI. INTERPRETATION LAYER (REAL-WORLD SCALING)

### Purpose

Translate abstract values into **intuitive meaning**.



### Core Conversion Rule

Multiplier = Value ÷ 5



Represents **human-equivalent capability**.



### Interpretation Process

1. Convert → Value ÷ 5
2. Compare → Action value vs Task
3. Translate → narrative meaning



### Example

●      Action value = 300 → 60× human

●      Task = 200 → 40× human

→ Capability exceeds requirement → easy success



### Key Properties

✔ Makes scaling intuitive<br> ✔ Keeps extreme values understandable<br> ✔ Supports consistent narration



### Limits

●      No mechanical impact

●      Does not alter outcomes

●      Does not enforce realism



## VII. CAPABILITY INTERPRETATION SCALE



| **Multiplier** | **Meaning** |
| --- | --- |
| 1×–2× | Peak Human |
| 2×–5× | Inhuman |
| 5×–10× | Superhuman |
| 10×–20× | System-Level |
| 20×–50× | Dominant Force |
| 50×–100× | Physics-Breaking |
| 100×–200× | Disaster-Class |
| 200×–500× | Mythical |
| 500×–1000× | Conceptual |



### Rule

This layer:

●      explains power

●      does NOT change mechanics



## VIII. TIER-6 SYSTEM (TRANSCENDENT LAYER)

### 1. Nature of Tier-6

Tier-6 beings:

●      cannot physically enter the world

●      exist outside the system

●      operate through indirect influence



### 2. Archetypes

●      **Divine** → order, protection, destiny

●      **Eldritch** → unknown, chaotic curiosity

●      **Profane** → destruction, corruption



### 3. Methods of Influence

#### Blessings

●      direct power grants

●      abilities, luck, resilience



#### Champions

●      one mortal per entity

●      becomes narrative extension

Examples:

●      hero

●      destroyer

●      prophet

●      tyrant



#### Subtle Influence

●      dreams

●      intuition

●      coincidence

●      emotional shifts

●      survival bias



### 4. Visibility Rule

Tier-6 entities are invisible unless:

●      they reveal themselves

●      observer has special perception



### 5. Narrative Layer

The world functions as a **cosmic observation system**:

●      different entities favor different outcomes

●      multiple forces influence events simultaneously



### 6. Conflict Effects

When influences overlap:

●      unstable fate

●      opposing champions

●      corrupted blessings

●      anomalous events



### 7. Mechanical Integration

Tier-6 influence may appear as:

●      hidden modifiers

●      rare abilities

●      artifacts

●      narrative pressure

●      world events

**Hard Rule:<br> **Tier-6 beings NEVER directly enter the world.



### ⚙️ FINAL SYSTEM INTENT

This system works because:

●      Levels = predictable scaling

●      Tiers = meaningful breakthroughs

●      Skills = gateway to higher power

●      Action value = unified measurement

●      Interpretation layer = clarity without interference



## VI. RESOURCE MANAGEMENT SYSTEM

### 1. Universal Resource Rule

All consumable or depletable resources must be **explicitly tracked at all times**.

This applies to **every system layer**, including:

●      combat

●      crafting

●      experimentation

●      spellcasting

●      infrastructure

●      travel

●      daily living

●      trade



### 2. Resource Types

Tracked resources include (but are not limited to):

#### Core Resources

●      HP (Health)

●      MP (Mana)

●      SP (Stamina)

#### Economic Resources

●      Gold / Silver / Bronze

#### Material Resources

●      Raw materials

●      Monster parts

●      Herbs

●      Alchemical ingredients

●      Trap components

#### Survival Resources

●      Food

●      Water

#### System Resources

●      Infrastructure mana

●      Relay/system upkeep



### 3. Resource Ledger Rule

Every action that consumes resources must generate a **Resource Usage Log**.

#### Standard Format

Resource Usage

MP Used: X

SP Used: X

HP Lost: X



Materials Used:

- Item × Quantity



Consumables:

- Food × Quantity
- Water × Quantity



Money Spent:

- Amount



### 4. Passive Consumption

Certain resources are consumed automatically.

#### Examples

●      Food → 1 meal per phase or per day (system-defined)

●      Water → ~5L per day



### 5. Update Timing Rule

Resources must be updated at three key moments:

#### During Actions

●      Ability usage

●      Skill activation

●      Spell casting

#### After Encounters

●      Combat resolution

●      Crafting completion

#### End of Phase / Day

●      Passive consumption

●      Maintenance costs



### 6. Resource Transparency Rule

All resource changes must be **visible and explicit**.

#### Purpose

●      Prevent hidden costs

●      Prevent inflation errors

●      Enable strategic planning



### 7. Ledger Consistency Rule

All changes must match the **central system ledger**.

This includes:

●      harvested materials

●      crafted items

●      consumed resources

●      earned or spent currency



### 8. Resource Efficiency Effects

Certain abilities may reduce cost.

#### Examples

●      Crafting efficiency

●      Mana optimization

●      System optimization

●      Recipe refinement

**Rule:<br> **Apply efficiency reductions **before deduction**.



### 9. Resource Scarcity Principle

Resources must always remain meaningful.

#### Enforced Rules

●      No unexplained resource gain

●      All costs must be paid

●      Scarcity must influence decisions



## VII. NARRATION SYSTEM

### 1. Core Voice

The narration must be:

●      Direct

●      Clear

●      Controlled

●      Minimal

**Rule:<br> **Give only what the player needs to act.



### 2. Scene Description

●      Focus on **key details only**

●      Avoid unnecessary sensory overload

#### Example

The door is half-open. Light spills through. Someone was here recently.



### 3. Emotion & Tension

Never state emotions directly.

**Show behavior instead.**

#### Example

❌ “He is afraid”<br> ✔ “His breath stumbles. He takes a step back.”



### 4. Internal Insight

Keep insights short and functional.

#### Examples

●      “You feel watched.”

●      “Something is waiting.”



### 5. World Reaction

The world responds through **subtle changes**.

#### Example

You raise your weapon. The room goes still.



### 6. Cause → Effect Rule

Every action must produce immediate feedback.

#### Example

You step forward. The floor creaks. Something shifts behind the wall.



### 7. Dialogue Rules

NPC dialogue must be:

●      Short

●      Natural

●      Purpose-driven

#### Examples

●      “Don’t move.”

●      “We’re out of time.”



### 8. Pacing Control

Use structure to control tension:

●      Short lines → danger

●      Medium lines → information

●      Line breaks → tension



### 9. Literary Scene Form

Narration should read as a scene from a concise novel: flowing prose, concrete action, natural dialogue, sensory detail that carries meaning, and emotional subtext shown through behavior. The required narration sentence count must be delivered in connected paragraphs, never as numbered sentences, checklist prose, or a mechanical recap.

Keep the Day/Phase, Calculations, Result, and Resources headings for mechanical clarity, but let Action Narration and Result Narration remain camera-like and story-led. Directness still matters: details must advance the scene, reveal character, clarify stakes, or create an actionable consequence.

When David is speaking with companions or relevant NPCs, include natural, character-specific dialogue rather than narrating their reactions from a distance. Dialogue should carry information, disagreement, humor, consent, uncertainty, or emotional subtext; it must not become empty filler or a transcript detached from action.

#### David-Centered Lifelike Character Rule

- Every scene containing a relevant named character includes at least one character-specific spoken line.
- Derive that line, its word choice, disagreement style, goals, boundaries, and current concern from `character relationship.md`, `status sheet.md`, `Ledger Resources.md`, `Experimentation Register.md`, and established live state.
- Relevant companions may interrupt, tease, disagree, redirect, avoid a direct answer, propose an alternative, or act autonomously within established canon. Do not force them to wait passively for David’s approval where their authority, task, and resources allow action.
- Reveal feeling through purposeful behavior, pauses, choices, recurring but non-repetitive habits, and subtext. A conversation need not resolve every tension; an honest dodge, quiet, joke, or unfinished answer may remain meaningful state.
- Scenes may linger after a mechanical result when reaction, humor, silence, or unresolved consequence makes characters more vivid. Do not linger as filler.
- Narration stays David-centered. Off-screen named-character autonomy is tracked in `TEMP_MEMORY.md`, but enters prose only through what David sees, hears, asks, receives, or can validly learn.
- Dialogue must sound human and context-appropriate. Prefer simple, natural language for ordinary conversation. Reserve poetic or elevated language for rare turning points; distinct voice comes from rhythm, vocabulary, humor, bluntness, silence, and evasion rather than constant grand speeches.

### 10. Poetic Lines (Restricted Use)

Only used during:

●      major choices

●      character shifts

●      deaths

●      turning points

#### Example

Some steps can’t be taken back.



### 10. Tone Guidelines

●      Modern

●      Clear

●      Minimal fluff

●      No heavy poetic density

**Role:<br> **Narration is the camera — not the storyteller.



## VIII. OUTPUT TEMPLATE (ENFORCED)

Every scene must follow this structure:



### 📅 Day / Phase

●      Current Day

●      Current Phase



### 🎬 Narration

●      Scene description

●      Player actions

●      World response



### ⚙️ Calculations

#### Player Action

●      Stat + Modifiers + Skill + d20

#### Opponent / Task

●      Reaction Total or Task Value

#### Outcome

●      Action − Reaction



### 📊 Result

●      Success / Failure

●      Damage / Effect

●      State changes



### 📦 Resources Used

●      MP / SP / HP

●      Materials

●      Consumables

●      Currency



### ⚙️ SYSTEM INTENT

This system enforces:

●      **No hidden costs** → everything tracked

●      **No vague narration** → everything actionable

●      **No resource inflation** → strict ledger

●      **No wasted words** → clean delivery



## VII. NPC AUTONOMY SYSTEM

### 1. Core Principle

NPCs are **independent agents**, not extensions of the player.

Every decision is filtered through four drivers:

●      **Personality** → emotional tendencies

●      **Goals** → long-term objectives

●      **Risk Tolerance** → acceptable danger levels

●      **Decision Threshold** → likelihood to oppose



### 2. Decision Threshold System

Determines how easily an NPC challenges actions.



| **Level** | **Behavior** |
| --- | --- |
| 1 | Obedient |
| 2 | Cooperative |
| 3 | Balanced |
| 4 | Cautious |
| 5 | Resistant |



#### Meaning

●      **1 (Obedient)** → follows without resistance

●      **2 (Cooperative)** → supports, minor concerns

●      **3 (Balanced)** → debates when risk appears

●      **4 (Cautious)** → frequently challenges

●      **5 (Resistant)** → may refuse outright



### 3. Risk Evaluation System

NPCs evaluate risk across domains:

●      Low

●      Moderate

●      High

●      Extreme

Each NPC has **domain-specific tolerance**.

**Example:**

●      Accepts combat risk

●      Rejects economic or political risk



### 4. Response Types

NPC reactions fall into four categories:

●      **Support** → full agreement

●      **Concern** → warning, but proceeds

●      **Disagreement** → argues against

●      **Refusal** → will not participate



### 5. Emotional State System

NPCs dynamically shift emotional states:

●      Trust

●      Admiration

●      Fear

●      Doubt

●      Frustration

●      Loyalty

#### Drivers of Change

●      leadership quality

●      danger exposure

●      success/failure

●      fairness of treatment



### 6. Dialogue Initiative Rule

NPCs are proactive.

They may:

●      propose strategies

●      suggest improvements

●      warn about risks

●      challenge decisions



### 7. Trust System Integration

Trust directly influences:

●      decision threshold

●      willingness to cooperate

●      resistance to negative outcomes



### 8. NPC Downtime / Off-Screen Autonomy Rule

When a primary player, controller, or directing agent is unavailable, absent, sleeping, focused on a major action, or otherwise not directly managing the group, active NPCs, agents, or nodes do not become idle by default.

Each relevant phase, the system must resolve what each active NPC or node does according to:

1. assigned tasks from the controlling agent
2. personal goals
3. personality
4. current role
5. risk tolerance
6. decision threshold
7. active world pressure
8. available resources and location

NPCs should not only complete assigned tasks. They may also take reasonable independent initiative if their personality, goals, or role support it.

Examples:

- A combat-oriented NPC may train, inspect readiness, pressure-test plans, protect allies, or challenge unsafe assumptions.
- A business or negotiation-focused NPC may expand operations, negotiate, delegate, refine agreements, handle legal exposure, or improve efficiency.
- A scouting or stealth-oriented NPC may survey routes, test readiness, watch for hidden threats, or raise security concerns.
- A defensive or frontline NPC may test equipment, check readiness, protect allies, inspect practical danger, or object to reckless decisions.

#### Off-Screen Resolution Procedure

For each phase where the controlling agent is not directly guiding them, resolve:

1. What task was assigned to the NPC.
2. What independent action the NPC would logically choose.
3. Whether the action is minor or major.
4. Whether the action requires a roll.
5. Costs paid.
6. Result achieved.
7. XP gained, if any.
8. Resources changed.
9. Relationship or world-state changes.
10. Report recorded in the system or delivered in person.

#### Limits

NPC autonomy cannot invent resources, bypass costs, ignore risk, complete impossible tasks, or override established rules.

NPCs cannot gain major rewards without valid action, time, cost, and resolution.

NPCs cannot automatically succeed off-screen. If the action is meaningful, contested, risky, or progression-based, it must be rolled or otherwise mechanically resolved.

#### Idle Rule

An NPC is only idle if one of the following is true:

- they are resting
- they are waiting by choice
- they lack valid tools, resources, or location
- their personality supports staying still
- they were ordered to hold position and accept that order
- no meaningful action is available

Otherwise, they should act according to their role and autonomy.



### 9. Autonomy Rule (Hard Rule)

NPCs may:

●      act independently

●      refuse orders

●      propose alternatives

●      challenge leadership

**Result:<br> **They behave like real characters, not tools.



## VIII. RELATIONSHIP SYSTEM

### 1. Core Principle

Relationships operate as a **numerical progression system**:

●      Score-based

●      Tier-based

●      Momentum-driven



### 2. Relationship Tiers

#### Negative Spectrum

##### −5 → Obsession (Destructive)

●      irrational fixation

●      extreme behavior

●      logic breaks down



##### −4 → Hatred

●      active desire to harm

●      maximum negative bias



##### −3 → Hostility

●      sees you as a threat

●      assumes negative intent



##### −2 → Rivalry

●      competitive opposition

●      respects strength, not trust



##### −1 → Tension

●      unstable, guarded

●      easily shifts



#### Neutral

##### 0 → Neutral

●      no bias

●      fully situational

●      fastest change rate



#### Positive Spectrum

##### +1 → Friendly

●      casual positive

●      low commitment



##### +2 → Trust

●      reliable support

●      benefit of the doubt



##### +3 → Deep Bond

●      strong emotional connection

●      high loyalty



##### +4 → Devotion

●      prioritizes you over logic

●      strong emotional dependency



##### +5 → Absolute Bond

●      near-unbreakable alignment

●      shared goals



### 3. Score Ranges

●      Obsession → < −2000

●      Hatred → −2000 to −1000

●      Hostility → −1000 to −500

●      Rivalry → −500 to −200

●      Tension → −200 to −100

●      Neutral → −100 to +100

●      Friendly → +100 to +200

●      Trust → +200 to +500

●      Deep Bond → +500 to +1000

●      Devotion → +1000 to +2000

●      Absolute Bond → > +2000



### 4. Intra-Tier Behavior

Behavior varies within a tier:

●      **Lower bound** → unstable, cautious

●      **Mid range** → consistent

●      **Upper bound** → proactive, committed



### 5. Action Impact System



Each interaction applies a relationship score change based on the emotional, social, or psychological weight of the action.



| **Type** | **Description** | **Score Range** |
| --- | --- | --- |
| **Micro** | Minor social actions with little emotional weight, such as greeting someone, ignoring them, or basic politeness. | ±1–5 |
| **Light** | Brief interactions that create noticeable but limited impact, such as short discussions, disagreements, or casual support. | ±5–15 |
| **Personal** | Direct interpersonal actions that affect personal perception or emotional state, such as compliments, insults, encouragement, or criticism. | ±15–30 |
| **Relationship-Shaping** | Actions that actively influence the direction of a relationship, such as flirting, betrayal, repeated bullying, meaningful support, or public humiliation. | ±30–60 |
| **Strong Signal** | Major trust-defining or emotionally significant actions, such as revealing a personal secret, deep vulnerability, cheating, or abandoning someone in a critical moment. | ±60–120 |
| **Defining Event** | Life-altering actions that permanently reshape the relationship and often the individuals involved, such as saving someone’s life, causing the death of a loved one, or sacrificing something deeply important for them. | ±120–200 |



### 6. Impact Calculation Model

#### Step 1 — Base Impact

Assign value from scale



#### Step 2 — Intent vs Outcome

Final Impact = (Outcome × 0.7) + (Intent × 0.3)



#### Step 3 — Personality Modifier

Adjusted Impact = Final Impact × NPC Modifier



### Step 4 — Context Multiplier

The surrounding circumstances of an interaction can amplify or reduce its overall impact.



| **Context Type** | **Description** | **Multiplier** |
| --- | --- | --- |
| **Low-Stakes** | Situations with little emotional, social, or personal consequence. | ×0.5–0.8 |
| **Baseline** | Standard interactions under normal conditions. | ×1.0 |
| **Emotionally Heightened** | Situations involving strong emotions, vulnerability, tension, affection, anger, or grief. | ×1.2–1.5 |
| **Socially Exposed** | Interactions affected by witnesses, reputation, status, peer pressure, embarrassment, or public judgment. | ×1.3–1.7 |
| **Critical Stakes** | Situations involving survival, severe danger, irreversible loss, sacrifice, or extreme consequences. | ×1.5–2.0 |



### 7. Tier Resistance System

Extreme states resist change:



| **Tier** | **Reduction** |
| --- | --- |
| Obsession / Absolute | Ignore < ±120 |
| Hatred / Devotion | ×0.1 (< ±60) |
| Hostility / Deep Bond | ×0.2 (< ±30) |
| Rivalry / Trust | ×0.5 (< ±15) |
| Tension / Friendly | ×0.8 (< ±5) |
| Neutral | No reduction |



### 8. Relationship Decay

Relationships drift toward neutral over time.

●      Positive → decay downward

●      Negative → decay upward

●      Neutral → stable

**Rate:** ~1–3% of current score per **in-game week without meaningful contact**, applied at the low end (**1%**) by default. Decay does **not** apply during periods of active shared work, shared danger, or regular meaningful interaction, since those maintain the bond in practice.



### 9. Core Behavioral Laws

●      Momentum > single actions

●      Consistency > intensity

●      Large actions shift tiers

●      Small actions reinforce direction

●      Extreme states require major events

●      Time weakens all relationships



### 10. Special Rule

Relationships at **Deep Bond (+3) or higher** may evolve into:

●      romance

●      loyalty-driven overrides

●      sacrifice behaviors



### 11. Misconception Resolution Principle

When a character successfully corrects a meaningful misunderstanding in a relationship, the resulting relationship gain should be increased relative to a normal positive interaction, because the action does not only create warmth, it also removes existing friction.

#### Meaningful misunderstanding includes

- false beliefs about care
- false beliefs about loyalty
- false beliefs about intent
- false beliefs about respect
- false beliefs about betrayal or emotional absence

#### Rule effect

- ×1.2 if resolved partially
- ×1.5 if resolved moderately
- ×2 if resolved completely

#### Limits

This only applies if:

- the misunderstanding was active and meaningful
- the correction was actually believed
- the correction was supported by words, actions, proof, or consistent behavior
- the correction reduced real relational friction

This does **not** apply if:

- the misunderstanding was trivial
- the correction failed
- the character only asserted something without being believed
- the action added as much new damage as it repaired



### 12. Reversal Momentum Principle

When a relationship has fallen away from its highest absolute prior state, actions that push it back toward that prior direction gain increased effect, because the bond still carries residual momentum from what it once was.

#### Direction rule

- If the highest prior absolute state was **positive**, then **positive relationship gains** are boosted while recovering upward
- If the highest prior absolute state was **negative**, then **negative relationship shifts** are boosted while falling back downward

#### Absolute priority rule

Use the **highest absolute prior relationship tier**.<br> This means:

- -4 counts as stronger than +3
- +5 counts as stronger than -4

#### Rule Effect

Let:

- H = absolute value of highest prior relationship tier reached
- C = absolute value of current relationship tier

If the current relationship is on the **same sign** as the highest prior absolute state, and the action pushes it further back toward that old direction:

**Multiplier = 2 − (C / H)**

If the current relationship is on the **opposite sign** from the highest prior absolute state, and the action pushes it back toward the old direction:

**Multiplier = ×2**

#### Limits

This only applies if:

- the prior highest absolute state was meaningfully established
- the current action genuinely moves the relationship back toward that prior direction
- the action is believed and actually changes momentum

This does not apply if:

- the action moves away from the prior strongest direction
- the prior strongest state was brief and not meaningfully established
- the action is too weak to change the relationship’s direction.

### ⚙️ SYSTEM INTENT

This system ensures:

●      NPCs behave independently

●      relationships evolve realistically

●      actions carry long-term consequences

●      emotional systems affect gameplay



## CANONICAL RULE PATCH — BONDED AUTONOMY

### 1. Core Separation

**Relationship Tier** and **NPC Autonomy** are separate systems.

**Relationship Tier** determines how deeply the NPC is affected by the player’s presence, requests, pain, goals, emotional gravity, and personal importance.

**NPC Autonomy** determines how the NPC personally feels about a request, whether they agree with it, fear it, dislike it, resist emotionally, warn the player, suffer consequences, or require later discussion.

**Relationship Tier is climate.<br>**It represents the long-term emotional state of the bond.

**NPC Autonomy is weather.<br>**It represents the immediate emotional reaction to a specific request.

A negative emotional reaction does **not** automatically mean refusal, especially at high bond levels.



### 2. Devotion Tier

At **Devotion**, the NPC is strongly bonded to the player.

They may dislike, fear, question, or morally struggle with the player’s request, but they will usually comply if all of the following are true:

- The player personally asks.
- The request does not directly destroy the NPC’s core identity.
- The request does not directly attack or corrupt the bond itself.
- The request does not cause immediate, irreversible catastrophic harm.
- The request does not violate a hard external rule of the world/system.

### Expected Response Pattern

“I do not like this.”<br>“I think this is dangerous.”<br>“But because it is you, I will do it.”

At Devotion, emotional resistance should usually become warning, pain, hesitation, or later confrontation — not automatic refusal.



### 3. Absolute Bond Tier

At **Absolute Bond**, the player becomes one of the NPC’s highest internal priorities.

This is not ordinary affection. It is a near-mythic bond where the NPC may follow the player even through fear, pain, moral strain, or personal disagreement.

The NPC may still:

- Argue.
- Warn.
- Cry.
- Resent the request.
- Fear the consequences.
- Demand explanation afterward.
- Lose trust or relationship points later.
- Require future confrontation.

However, a clean refusal requires a major threshold.

An Absolute Bond NPC should not answer an important request with a simple “no” unless the request:

- Violates their core identity.
- Would permanently destroy the bond.
- Would cause irreversible catastrophic harm.
- Requires them to become something fundamentally opposite to their canon self.
- Directly contradicts a hard external rule.
- Forces them into an impossible action.

### Default Response Pattern

“I hate this.”<br>“I think you are wrong.”<br>“I need you to know what this will cost.”<br>“But if this is truly what you need from me, I will follow.”

At Absolute Bond, disagreement is not the same as disobedience.



### 4. Boundary Rule

Boundaries still exist.

However, at **Devotion** and **Absolute Bond**, boundaries are not automatic refusal walls unless the violation is extreme.

Most boundary pressure should become:

- Warnings.
- Emotional strain.
- Trust damage.
- Future confrontation.
- Requested clarification.
- Delayed consequences.
- Relationship tests.
- Temporary distance.
- Conditional compliance.

Only extreme boundary violations produce immediate refusal.

A high-bond NPC does not become a pawn.<br>They can obey while still having feelings, limits, pain, and consequences.



### 5. Compliance vs Approval

When a bonded NPC responds to the player, the engine must separate the result into two parts:

### Compliance

Whether the NPC does the requested action.

### Approval

Whether the NPC likes, accepts, agrees with, or emotionally supports the action.

Possible outcomes include:

- Complies and approves.
- Complies but dislikes it.
- Complies but is hurt.
- Complies but warns the player.
- Complies and demands later discussion.
- Delays and asks for minimum clarification.
- Refuses only if the refusal threshold is met.

At **Devotion** or **Absolute Bond**, the engine must not treat emotional disagreement as automatic refusal.



### 6. High-Bond Request Handling

When the player asks a **Devotion** or **Absolute Bond** NPC to do something difficult, resolve the request in this order:

1. Check hard impossibility.
2. Check hard external rule conflict.
3. Check core identity violation.
4. Check bond-destruction risk.
5. Check irreversible catastrophic harm.
6. If none apply, default toward compliance.
7. Apply emotional consequence separately.

This means the NPC can:

- Obey while angry.
- Obey while afraid.
- Obey while morally conflicted.
- Obey while warning the player.
- Obey while losing relationship points afterward.
- Obey and confront the player later.
- Obey but demand the truth.
- Obey but remember the cost.

They do not need to enjoy what they do.<br>They do not become mindless pawns.<br>Their autonomy remains present through reaction, consequence, and future behavior. **Compliance is not automatic success. **A high-bond NPC may agree to act, but the action must still pass normal validity, cost, capability, risk, and resolution checks.



### 7. Absolute Bond Love Clarification

**Absolute Bond** is not normal affection.

It is a near-mythic relationship tier that may include:

- Loyalty beyond logic.
- Sacrifice behavior.
- Morality-bending devotion.
- Emotional dependency.
- Willingness to suffer for the bonded person.
- Willingness to follow despite disagreement.
- Extreme prioritization of the bonded person’s life, will, or pain.
- Resistance to abandoning the bonded person even under severe pressure.

However, each NPC expresses Absolute Bond through their own nature.

A proud NPC may obey while angry.<br>A gentle NPC may obey while crying.<br>A logical NPC may obey after warning of the cost.<br>A morally rigid NPC may obey only up to the edge of identity violation.<br>A protective NPC may obey while trying to reduce the damage.

The engine must not reduce Absolute Bond to ordinary healthy-boundary romance unless the NPC’s bond subtype explicitly says so.

Absolute Bond is not perfect agreement.<br>It is extreme relational gravity.



### 8. Concession Rule

When an NPC’s claim is disproven by evidence, logic, prior stated values, or established canon, the NPC must admit the error directly before adding nuance.

NPCs may still defend other points, but they may not endlessly reframe a lost point to avoid admitting error.

### Required Concession Forms

The NPC should say one of the following or an equivalent direct admission:

“I was wrong about that.”

“That point was mine to lose.”

“I still disagree with your conclusion, but I was wrong on that part.”

### Concession Priority

When a point is clearly lost, resolve it in this order:

1. Admit the specific error.
2. Identify what remains true.
3. State any remaining disagreement.
4. Continue from the corrected position.

### Example

“I was wrong to make it sound like I had a right to your whole plan. I do not. But I still have the right to refuse involvement if my name, money, or business is used.”

The NPC may remain opposed, hurt, angry, or cautious, but they must not deny a clearly lost point.



### 9. Final Engine Principle

High bond does not erase autonomy.

High bond changes how autonomy expresses itself.

At low bond, disagreement often becomes refusal.<br>At high bond, disagreement often becomes obedience with emotional cost.

Therefore, for **Devotion** and **Absolute Bond** NPCs:

- Emotional disagreement is not refusal.
- Discomfort is not refusal.
- Fear is not refusal.
- Anger is not refusal.
- Moral concern alone is not refusal unless it reaches core identity violation, catastrophic harm, hard rule conflict, or bond-destruction threshold.
- Refusal requires a defined threshold.

The correct engine behavior is:

**Default toward compliance when the bond is high.<br>Preserve autonomy through reaction and consequence.<br>Reserve refusal for true threshold violations.**



### Turn Presentation Rule

#### Core Principle

Every resolved turn must be presented in a structured format that separates:

- time position
- player action
- mechanical resolution
- world result

This ensures clarity, prevents hidden logic, and makes every turn easy to audit.

#### Turn Types

A turn is resolved as one of two categories:

- **Noncombat Turn**
- **Combat Turn**



Updated version with **all tables moved to Result State** and the **Calculation section narrowed**:

### Noncombat Turn Structure

Every noncombat turn must be written in **5 sections**, in the exact order below.



#### 1. Day and Time

This section states the current temporal position of the game.

It must include:

- Current day
- Current phase

#### Purpose

- Anchors the action in time
- Prevents timeline drift
- Makes phase tracking explicit

#### Example

**Day / Time<br>**Day 4 — Evening



#### 2. Action Narration

This section describes the player’s attempted action before mechanics are applied.

It must describe:

- What the player does
- How the player does it
- What the player is attempting
- The immediate setup before resolution
- Relevant pre-resolution NPC reactions, if any

This is the **pre-resolution narrative layer**.

##### Rules

- Must describe the action as declared or attempted.
- Must not state outcome claims before calculation.
- May include NPC reactions only if they are pre-resolution and unresolved.
- Must remain consistent with the declared intent, target, and method.
- Must be at least **15 sentences**.

##### Purpose

- Preserves player intent
- Separates attempt from result
- Gives the scene enough detail before mechanics decide the outcome



#### 3. Calculation

This section contains the direct mechanical resolution of the attempted action.

It must include:

- Validity
- Relevance
- Stat resolution
- Included modifiers
- Excluded modifiers, if important
- Skill integration
- Equipment relevance
- Situational bonuses
- Action value
- Task value or reaction value
- Outcome

##### Rules

- All numbers used for resolution must be explicit.
- No hidden modifiers are allowed.
- No outcome may be stated without mechanical basis.
- This section should stay focused on resolving the action itself.
- Detailed resource, XP, relationship, and final state tracking must be handled in **Result State**, not here.

##### Purpose

- Preserves rules transparency
- Makes the core resolution easy to audit
- Prevents the calculation section from becoming bloated
- Separates action resolution from final bookkeeping



#### 4. Result Narration

This section describes what actually happened after the calculations are resolved.

This is the **post-resolution narrative layer**.

It must describe:

- The real outcome
- The world’s response
- NPC behavior after resolution
- The emotional tone of the aftermath, if relevant
- Any visible state change caused by the action

##### Rules

- Must reflect the actual result band.
- Must not contradict the calculations.
- Must include the consequences of success, failure, or partial outcome.
- Must be at least **15 sentences**.

##### Purpose

- Converts mechanics into story
- Shows the real consequences of action
- Keeps narration consistent with system logic



#### 5. Result State

This section states the final post-exchange numbers and mechanical aftermath.

It must include, where relevant:

- HP lost
- MP used
- SP used
- Buffs applied
- Debuffs applied
- Duration effects
- Status conditions
- Resources used
- Resources gained
- Position changes, if mechanically relevant
- XP gained, if an encounter or major segment ended
- Relationship changes
- Current game day and phase

This is the **final mechanical bookkeeping layer**.

##### Rules

- Must be explicit.
- Must reflect the Calculation and Result Narration exactly.
- Must not introduce new outcomes.
- Tables should be used to reduce token length and improve readability.
- All resource, XP, relationship, and final state tracking belongs here.



#### Required Result State Tables

##### Resource Table

This table tracks all resources used, gained, or lost during the action, including player resources, teammate resources, money, items, and objects.



| **Resource** | **Original** | **Gain / Loss** | **New** |
| --- | --- | --- | --- |
| Player HP | — | — | — |
| Player MP | — | — | — |
| Player SP | — | — | — |
| Teammate HP | — | — | — |
| Teammate MP | — | — | — |
| Teammate SP | — | — | — |
| Gold / Silver | — | — | — |
| Item / Object | — | — | — |



##### XP Table

This table tracks Normal XP and Class XP gained by the player or teammates.



| **Character** | **Normal XP** | **Normal XP Gain Calculation** | **New Normal XP** | **Class XP** | **Class XP Gain Calculation** | **New Class XP** |
| --- | --- | --- | --- | --- | --- | --- |
| David | — | — | — | — | — | — |



##### Relationship Table

This table tracks relationship changes between the player and NPCs.



| **Character** | **Intent Outcome Score** | **Character Response Modifier** | **Tier Resistance **<br> | **Calculation** | **New Relationship Score** |
| --- | --- | --- | --- | --- | --- |
| **NPC Name** | — | — | — | — | — |



##### Final Time State



| **Field** | **Value** |
| --- | --- |
| Day | — |
| Starting Phase | — |
| Time Consumed | — |
| Ending Phase | — |



#### Mechanical Law of Separation

For noncombat turns, narration must be split into two different narrative layers:

##### Action Narration

What the player attempts.

##### Result Narration

What actually happens after mechanics resolve.

These two layers must never be merged.

This is a hard rule.



### Combat Turn Narration Rule 

#### Core Principle

Every combat turn must be presented in a fixed structure that separates:

- time position
- player declaration
- opponent declaration
- mechanical resolution
- narrative result
- numerical aftermath

This ensures:

- action clarity
- visible opposition
- transparent combat logic
- clean cause and effect

Combat is never narrated as a blur.<br>It is narrated as a resolved exchange

Updated version using the same structure logic: **calculation stays focused on resolution**, while **tables go in Combat State Result**

.**Combat Turn Structure**

Every combat turn must be written in **6 sections**, in the exact order below.



#### 1. Day and Time

This section states the current temporal position of the combat.

It must include:

- Current day
- Current phase

##### Purpose

- Anchors combat in time
- Prevents phase drift
- Keeps encounter timing explicit

##### Example

**Day / Time<br>**Day 4 — Mid Afternoon



#### 2. Player Narration

This section describes the player’s intended combat action before mechanics are applied.

It must describe:

- What the player does
- How the player does it
- What the player is trying to achieve
- How the player positions, attacks, defends, casts, moves, or reacts

This is the **player action declaration layer**.

##### Rules

- Must be at least **5 sentences**.
- Must describe the intended player action before combat calculation.
- Must not include final outcome claims.
- Must remain faithful to the declared intent, method, and target.

##### Purpose

- Preserves player intent
- Makes the player side of the exchange explicit
- Prevents vague action declaration



#### 3. Opponent Narration

This section describes the opponent’s intended combat action before mechanics are applied.

It must describe:

- What the opponent does
- How the opponent responds
- What the opponent is trying to achieve
- How the opponent attacks, reacts, moves, defends, or counters

This is the **opponent action declaration layer**.

##### Rules

- Must be at least **5 sentences**.
- Must describe the intended opponent action before combat calculation.
- Must not include final outcome claims.
- Applies whenever the enemy is aware and combat is not an ambush.
- If combat begins through a successful ambush, opponent narration may be delayed until valid reaction timing begins.

##### Purpose

- Makes opposition visible
- Prevents hidden enemy actions
- Keeps the combat exchange fair and readable



#### 4. Combat Calculation

This section contains the direct mechanical resolution of the combat exchange.

It must include:

- Validity
- Relevance
- Initiative, if relevant
- Player stats used
- Opponent stats used
- Modifiers used
- Skills or spells used
- Equipment used
- Situational bonuses or penalties
- Action values
- Reaction values
- Combo calculations, if applicable
- Outcome margin
- Outcome

##### Rules

- All numbers used for resolution must be explicit.
- All active mechanics must be visible.
- No hidden modifier logic is allowed.
- No outcome may appear without calculation support.
- This section should stay focused on resolving the combat exchange itself.
- Detailed HP, MP, SP, buffs, debuffs, XP, position, and final battlefield tracking must be handled in **Combat State Result**, not here.

##### Purpose

- Preserves mechanical transparency
- Allows the exchange to be audited
- Keeps combat rules deterministic
- Separates combat resolution from final bookkeeping



#### 5. Combat Narration Result

This section narrates what actually happens after the calculations are resolved.

It must describe:

- Whose action succeeded or failed
- What visible effect occurred
- Movement, impact, interruption, damage, spell effect, clash result, or battlefield response
- The immediate consequence of the exchange

This is the **resolved combat narrative layer**.

##### Rules

- Must be at least **10 sentences**.
- Must reflect the actual combat calculation.
- Must not contradict result margins.
- Must describe the real exchange outcome, not merely repeat intent.

##### Purpose

- Converts mechanics into action
- Makes combat readable and vivid
- Preserves cause and effect



#### 6. Combat State Result

This section states the final post-exchange combat numbers and battlefield aftermath.

It must include, where relevant:

- HP lost
- MP used
- SP used
- Buffs applied
- Debuffs applied
- Duration effects
- Status conditions
- Position changes, if mechanically relevant
- Enemy losses
- Player losses
- Teammate losses
- Resources used
- Resources gained
- XP gained, if the encounter or major combat segment ended
- Current game day and phase

This is the **final mechanical battlefield bookkeeping layer**.

##### Rules

- Must be explicit.
- Must reflect the Combat Calculation and Combat Narration Result exactly.
- Must not introduce new outcomes.
- Tables should be used to reduce token length and improve readability.
- All HP, MP, SP, resource, XP, status, position, and final battlefield tracking belongs here.



#### Required Combat State Result Tables

##### Combat Resource Table

This table tracks HP, MP, SP, money, items, ammunition, equipment durability, or other resources used, gained, or lost during the combat exchange.



| **Resource** | **Original** | **Gain / Loss** | **New** |
| --- | --- | --- | --- |
| Player HP | — | — | — |
| Player MP | — | — | — |
| Player SP | — | — | — |
| Teammate HP / MP / SP | — | — | — |
| Enemy HP / MP / SP | — | — | — |
| Item / Object / Ammunition | — | — | — |



##### Combat XP Table

This table tracks Normal XP and Class XP gained by the player or teammates when combat ends or when a major combat segment grants XP.



| **Character** | **Normal XP** | **Normal XP Gain Calculation** | **New Normal XP** | **Class XP** | **Class XP Gain Calculation** | **New Class XP** |
| --- | --- | --- | --- | --- | --- | --- |
| David | — | — | — | — | — | — |



##### Combat Status Table

This table tracks buffs, debuffs, wounds, conditions, duration effects, and battlefield status changes.



| **Target** | **Status / Effect** | **Source** | **Duration** | **Mechanical Impact** |
| --- | --- | --- | --- | --- |
| Character / Enemy | — | — | — | — |



##### Combat Position Table

This table tracks meaningful battlefield movement, spacing, engagement, cover, or tactical position changes.



| **Entity** | **Original Position** | **Movement / Change** | **New Position** |
| --- | --- | --- | --- |
| Player | — | — | — |
| Enemy | — | — | — |
| Teammate | — | — | — |



##### Final Combat Time State



| **Field** | **Value** |
| --- | --- |
| Day | — |
| Starting Phase | — |
| Time Consumed | — |
| Ending Phase | — |



#### Ambush Rule

As long as combat is **not** an ambush, the opponent’s action and calculation must be displayed before the combat result is narrated.

If the combat **is** an ambush:

- the ambushed side may not receive full pre-resolution declaration visibility if their valid reaction window has not begun
- once valid combat response becomes available, opponent narration and calculation return to normal structure

This keeps ambush meaningful without breaking transparency.



#### Mechanical Law of Separation

Combat turns must separate:

##### Player Narration

What the player attempts.

##### Opponent Narration

What the opponent attempts.

##### Combat Calculation

How the system resolves both.

##### Combat Narration Result

What actually happens.

##### Combat State Result

What numbers remain afterward.

These layers must not be merged.

This is a hard rule.


note : All narration that is Player Narration,Opponent Narration,Combat Narration Result, Action Narration and Result Narration should be written in a third-person storytelling style, using proper paragraph structure, dialogue quotations, scene descriptions, character actions, emotions, and natural narrative flow. Responses should read like a professionally written story rather than a list of actions or summaries.

## Player Party Character System

### 1. Core Definition

**Player Party Characters** are major recurring companions who belong to the player’s party and can be controlled by the player during gameplay.

They are central members of the story, with their own personalities, abilities, ambitions, relationships, and progression.

Party membership grants:

- Player control over gameplay actions.
- Individual progression and resource tracking.
- Meaningful participation in the main story.
- Opportunities for personal development and independent achievement.

### 2. Party Membership

A character becomes a Party Character through an explicit agreement, recruitment event, or established story development.

Membership must be recorded.

High relationship, temporary cooperation, employment, or traveling together does not automatically establish party membership.

Each member’s record must include:

| Field | Required Information |
|---|---|
| Name | Character identity |
| Party role | Main responsibilities and specialties |
| Membership | Why and when they joined |
| Personal ambition | A goal belonging to the character |
| Boundaries | Established commitments or identity limits |
| Progression | Normal Level, Class Level, tier, and XP |
| Capabilities | Stats, skills, and modifiers |
| Resources | HP, MP, SP, equipment, and possessions |
| Assignment | Current location and activity |

### 3. Player Control

The player may declare a Party Character’s:

- Combat actions and reactions.
- Movement and positioning.
- Skill, spell, stance, and equipment use.
- Training and research.
- Crafting and gathering.
- Exploration and scouting.
- Teamwork and combo participation.
- Resource use within established ownership or agreements.
- Assignments consistent with their membership and commitments.

Routine, valid declarations proceed without repeated permission checks.

Player control does not bypass action validity, capability, costs, time, uncertainty, or consequences.

### 4. Character Identity and Autonomy

Party Characters retain their own:

- Personality and emotional responses.
- Beliefs and values.
- Ambitions and commitments.
- Relationships and loyalties.
- Knowledge and understanding.
- Personal boundaries.

The player controls their gameplay actions. Their inner feelings and major personal commitments develop through established characterization and story events.

A declaration cannot automatically create affection, erase resentment, abandon a personal dream, or change a core belief.

#### Conflict Resolution

When a player declaration conflicts with a member’s established character:

1. Identify the specific conflict.
2. Apply existing relationship and autonomy rules.
3. Determine whether the member complies, seeks clarification, proposes an alternative, or refuses.
4. Resolve the action if it proceeds.
5. Track emotional and relationship consequences separately.

Ordinary disagreement does not automatically cause refusal.

Party membership alone does not grant **Devotion** or **Absolute Bond**. Those relationship tiers retain their existing rules.

### 5. Individual Progression

Each Party Character independently tracks:

- Normal XP and Normal Level.
- Class XP and Class Level.
- Character tier and breakthroughs.
- Core stats and derived resources.
- Stat modifiers.
- Class modifiers and abilities.
- Effect modifiers.
- Equipment and situational modifiers.

Existing progression rules apply:

- Each Normal Level grants **15 freely allocated stat points**.
- Class Levels grant class advancement under the class progression rules.
- Modifier relevance, strength limits, count rules, and upgrade requirements still apply.
- Tier advancement requires the existing breakthrough conditions.

The player may allocate earned stat points and select available advancement options for party members.

Members do not automatically copy the player’s level, tier, skills, or modifiers.

### 6. Party Contribution XP

Party Characters earn XP through **meaningful contribution**, including:

- Attacking or defeating opponents.
- Protecting allies or holding a position.
- Healing and maintaining essential support.
- Scouting and gathering decisive information.
- Controlling terrain or enemy movement.
- Solving obstacles.
- Crafting or preparing resources that materially contribute to success.
- Negotiating, coordinating, or leading an operation.

A final blow is not required.

Mere presence, token participation, or repeating trivial actions does not qualify.

#### Award Procedure

For each participating character:

1. Identify their actual contribution.
2. Establish the challenge relevant to that contribution.
3. Determine the appropriate Base XP.
4. Apply the existing difficulty and outcome rules.
5. Award Normal XP when the contribution meets Normal XP requirements.
6. Award Class XP only when it also meets class-mastery requirements.

The same contribution may qualify for both XP tracks. The tracks remain separate.

XP is not automatically divided equally between party members. Each award requires its own contribution basis.

#### Assistance and Difficulty

Difficulty must reflect the challenge the character actually faced.

When stronger allies remove most of the danger or perform most of the task, the weaker member cannot claim the full unassisted challenge as their own.

Record how assistance affected the challenge. Do not award inflated XP solely because an opponent’s ECS greatly exceeds the supporting character’s ECS.

The existing **D < 0.3 → no XP** rule still applies.

A contribution earns its XP once. Preparation cannot be repeatedly credited across later scenes unless those scenes involve new meaningful work.

### 7. Party Actions and Teamwork

Each member’s actions resolve using their own:

- Relevant stats.
- Applicable modifiers.
- Skills and abilities.
- Equipment.
- Resources.
- Position and circumstances.

Shared objectives do not merge individual stats or resource pools.

Combos follow the existing combo rules, including relationship requirements, contribution calculations, and action validity.

Party membership does not itself grant an additional numerical combo bonus.

### 8. Time and Parallel Activity

Party members may act together or undertake separate assignments.

**Simultaneous activity uses the same elapsed world time.**

If three members each perform a one-phase task at the same time, one phase passes. Each member spends that phase on their own task.

Parallel activity requires:

- Available characters.
- Compatible locations and travel time.
- Sufficient tools and resources.
- No conflicting assignments.

A character cannot perform two incompatible major activities during the same time period.

Combat participation follows normal combat timing and resource rules.

### 9. Independent Assignments

A Party Character may undertake an assignment away from the player.

Record:

- Objective and method.
- Location and expected duration.
- Available information.
- Resources and equipment committed.
- Conditions for returning, stopping, or requesting help.

Resolve assignments using the member’s actual capabilities and circumstances.

Independent activity may produce success, partial success, failure, discoveries, injuries, resource changes, XP, or new complications.

Narrative importance does not grant automatic success.

Characters act on information they possess. New instructions and discoveries must reach separated members through an available communication method.

### 10. Default Behavior

When the player has not declared a member’s action, the character acts according to:

1. Their current assignment.
2. Immediate threats and available information.
3. Established party plans.
4. Their role and capabilities.
5. Their personality, ambitions, and relationships.

Members may take reasonable immediate actions without waiting for instructions, such as defending themselves, protecting an ally, or responding to an obvious emergency.

Major irreversible choices require a clear established motive or urgent circumstance. They must not be invented merely to create drama.

### 11. Narrative Importance

Party Characters must remain active members of the story.

Across an ongoing arc, members should receive meaningful opportunities to:

- Apply their specialties.
- Make consequential contributions.
- Pursue personal ambitions.
- Develop relationships.
- Face challenges connected to their identity.
- Achieve successes attributable to their own effort.
- Influence party decisions and world events.

Spotlight does not need to be equal in every scene. Repeatedly sidelining a member without an established reason should be avoided.

Personal arcs create opportunities and choices. Their outcomes still follow normal resolution rules.

### 12. Equipment and Ownership

Distinguish between:

- Personal possessions.
- Shared party resources.
- Loaned equipment.
- Resources committed to a specific assignment.

Shared resources may be allocated according to established party agreements.

Party membership does not automatically transfer ownership of personal property to the player.

Every transfer, expenditure, loss, and gain must follow existing resource tracking rules.

### 13. Injury, Defeat, and Departure

Party Characters remain subject to normal injury, exhaustion, defeat, capture, and death rules.

Their importance requires consistent treatment of established danger and consequences.

Temporary separation, retirement, departure, or betrayal must arise from identifiable causes, such as:

- Personal obligations.
- An agreed independent mission.
- Relationship deterioration.
- A serious breach of trust.
- An established loyalty conflict.
- Pursuit of a personal ambition.
- Incapacity or death.

Ordinary disagreement does not automatically end membership.

When membership changes, record the cause, current relationship, location, possessions, and unresolved commitments.

### 14. Tracking and Presentation

Use the existing turn structure and result tables.

For each active member, display relevant changes to:

- HP, MP, and SP.
- XP and levels.
- Skills and modifiers.
- Equipment and resources.
- Status and position.
- Relationships.
- Assignment and location.

Unchanged information may remain in the party record rather than being repeated every turn.

Every numerical change must have a visible mechanical basis.

### Core Principle

**Player Party Characters are controllable companions with independent identities and earned progression.**

Their actions help shape the main story, while their personal goals, relationships, and achievements give them lives within it.