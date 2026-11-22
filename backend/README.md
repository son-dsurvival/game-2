# Background Phase System

This package handles time-driven world state and off-screen autonomy.

## Runtime flow

1. `PhaseClock` converts structured Lead Resolver time changes into one transition per entered phase.
2. `BackgroundStateStore` persists complete directives, ticks, and pending surprises in private `brain/state/background_state.json`, then mirrors only explicitly OOC-safe teammate/background status to `markdown_files/Experimentation Register.md`.
3. `WorldDirector` is the single world-progression owner. It advances private monster, NPC, faction, facility, and growth state in `brain/state/world_state.json`, schedules hidden events, and coordinates recurring processes from `brain/state/recurring_processes.json` and `brain/state/resource_formulas.json`.
4. `WorldDirector.plan_processes()` reads active processes, checks due positions, loads formula definitions, validates requirements, and builds the private handoff for the completed-day batch.
5. `WorldDirector.apply_entity_changes()` accepts only typed, Lead-approved entity deltas, rejects duplicates and immutable fields, clamps populations to zero/capacity, and records before/after history in private world state.
6. Phase background work queues resolved world-entity changes. At day-end, the completed-day world/process handoff is sent to the `resources` specialist and then to `BackendLeadResolver`; only an explicitly applied `process_results` entry advances a process schedule.
7. `AutonomyResolver` chooses an NPC's attempted action from its directive and current character state. It never assumes success.
8. `PhaseTickEngine` runs explicitly required autonomy lanes concurrently, marks the route as `backend_autonomy`, and sends the handoff to the dedicated `BackendLeadResolver`. That resolver decides private actor outcomes, then the engine commits only a resolved tick. Missing resolution leaves the tick retryable. World growth and recurring resource processes are committed separately in the approved day-end batch.
9. `VisibilityFilter` withholds roleplay-unrevealed events from narrator input. Private surprises are not mirrored to the player-readable register at all.
10. `contracts.py` contains JSON-safe data contracts shared by each component.

## Storage

`brain/state/background_state.json` is the authoritative runtime store for complete directives, phase ticks, and pending world surprises. `brain/state/world_state.json` is the authoritative private store for hidden world entities, queued world-entity changes, growth trajectories, and scheduled world events. `brain/state/recurring_processes.json` stores active process schedules and private process history; `brain/state/resource_formulas.json` stores named deterministic formula definitions and is written through `WorldDirector.upsert_formula()` or `save_formulas()`. These files are private runtime state and remain git-ignored. Phase actions queue typed world changes; the approved day-end batch applies automatic growth, queued changes, and recurring process results once. `Experimentation Register.md` is a player-readable **out-of-character mirror** containing only entries explicitly marked `ooc_visibility: teammate_status`, `background_status`, `ooc_visible`, or `public`. Unlabelled records default to private and are never mirrored. A roleplay-hidden entry in the mirror may be read OOC but is not character knowledge or Narrator material until revealed through play. The Markdown mirror contains no JSON blobs.

Each committed tick has an id such as `day-3-afternoon`. Replaying the same tick is safe: the store returns `already_committed` and does not apply it twice.

The engine does not call the Narrator. Call `VisibilityFilter.for_narrator()` only after the tick is resolved and only when the player-facing response is being assembled. Agent command intents are separate from world resolution: the Admin Agent may request safe slash commands through the outer runtime loop, while the Lead Resolver may request only `/end-day`; reset, cancellation, approval, character selection, and quit remain player-controlled.
