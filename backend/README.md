# Background Phase System

This package handles time-driven world state and off-screen autonomy.

## Runtime flow

1. `PhaseClock` converts structured Lead Resolver time changes into one transition per entered phase.
2. `BackgroundStateStore` persists complete directives, ticks, and pending surprises in private `brain/state/background_state.json`, then mirrors only explicitly OOC-safe teammate/background status to `markdown_files/Experimentation Register.md`.
3. `AutonomyResolver` chooses an NPC's attempted action from its directive and current character state. It never assumes success.
4. `PhaseTickEngine` runs the core specialist lanes concurrently, sends the plan to a resolver, and commits only a resolved tick. Missing resolution leaves the plan retryable.
5. `VisibilityFilter` withholds roleplay-unrevealed events from narrator input. Private surprises are not mirrored to the player-readable register at all.
6. `contracts.py` contains JSON-safe data contracts shared by each component.

## Storage

`brain/state/background_state.json` is the authoritative runtime store for complete directives, phase ticks, and pending world surprises. `Experimentation Register.md` is a player-readable **out-of-character mirror** containing only entries explicitly marked `ooc_visibility: teammate_status`, `background_status`, `ooc_visible`, or `public`. Unlabelled records default to private and are never mirrored. A roleplay-hidden entry in the mirror may be read OOC but is not character knowledge or Narrator material until revealed through play. The Markdown mirror contains no JSON blobs.

Each committed tick has an id such as `day-3-afternoon`. Replaying the same tick is safe: the store returns `already_committed` and does not apply it twice.

The engine does not call the Narrator. Call `VisibilityFilter.for_narrator()` only after the tick is resolved and only when the player-facing response is being assembled.
