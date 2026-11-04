# Pipeline Implementation Audit — Current State

## Scope and result

This document records the current implementation state after the runtime, persistence, editor, background-state, visibility, cache, and model-call changes made in this repository. It distinguishes implemented foundations from work still required for a fully playable end-to-end pipeline.

**Result:** the project now has safer persistence primitives and a resumable runtime-state skeleton. It is **not yet a completed live gameplay pipeline** because `pipeline.py` does not yet drive the entire player-turn loop from routing through narration, recording, day-end approval, and next-day world scheduling.

## 1. Implemented and corrected

### A. Shared model-call persistence — implemented

`brain/model_gateway.py` is now the only provider-facing layer for DeepSeek/OpenAI-compatible and Ollama calls.

It writes append-only private call records to:

```text
brain/state/model_calls.jsonl
```

Each record includes the stage, optional request/turn identity, normalized messages, model settings, cache key, response or error, and never an API key. Exact successful calls can be reused after restart; failed calls are recorded but never reused as successes.

The following model callers use the gateway:

- Turn Router
- Evidence Bundle action-frame extraction and selection
- Specialist Runner and JSON repair
- Gap Adjudicator
- Lead Resolver
- Narrator
- Recorder planner
- Evidence-index description tool
- Admin Agent

`trial/29_run_model_gateway_dummy.py` verifies success journaling, failure journaling, same-process reuse, restart reuse, and API-key exclusion.

### B. Incremental evidence indexing — implemented

`brain/build_evidence_index.py` now uses schema version 2. It reuses unchanged file roots based on source size and modification time, reparses only changed Markdown files, and assigns each section a `content_hash`.

`brain/describe_evidence_index.py` reads each source file at most once per run. Unchanged DeepSeek section descriptions are preserved, while only changed/missing descriptions need enrichment.

`trial/28_run_incremental_evidence_index_dummy.py` verifies unchanged-file reuse and section-level description preservation/invalidation.

### C, D, E. Version-bound transactional Admin Editor — implemented foundation

`outside game/approval.py` now provides:

- `bind_source_versions()` to freeze expected full-file hashes before approval.
- `proposal_digest()` to fingerprint reviewed proposal content.
- Approval attribution bound to that digest.

`outside game/admin_editor.py` now:

1. Rejects a changed proposal digest or unbound source versions.
2. Groups and composes all changes for the same target against one source snapshot.
3. Stages full original and updated file images under private transaction storage.
4. Replaces staged file images only after all changes validate.
5. Restores replaced files if a replacement fails.
6. Writes a private replay receipt so a successful retry returns the prior result rather than applying again.
7. Provides `recover()` for unfinished staged transactions on runtime resume.

`AdminAgent` version-binds its `proposal_ready` changes before returning them.

Remaining caution: the transaction primitive is implemented and covered by normal admin tests, but dedicated fault-injection tests for every crash point and audit-log failure path are still required before production use.

### F. Lossless private background state — implemented

`backend/background_state.py` now separates complete private runtime state from the player-readable OOC mirror.

Complete directives, full ticks, and pending world events are stored in:

```text
brain/state/background_state.json
```

`markdown_files/Experimentation Register.md` is no longer the backend source of truth. It receives only explicitly allowed teammate/background entries with one of:

```text
ooc_visibility: teammate_status
ooc_visibility: background_status
ooc_visibility: ooc_visible
ooc_visibility: public
```

Unlabelled entries default to private. True surprises, enemy plans, unrevealed world events, and complete private tick detail stay in `brain/state/`.

`trial/25_run_backend_dummy.py` verifies that a private world surprise remains in private state and is absent from the Experimentation Register mirror.

### G and H. Sequential ticks and fractional phase progress — implemented foundation

`PhasePosition` now includes:

```text
progress: 0.0 <= progress < 1.0
```

`PhaseClock` accepts fractional phase duration and emits a background transition only when a real phase boundary is crossed.

`PhaseTickEngine` now stops at the first unresolved phase rather than continuing into later phases. It can accept `next_context` from a resolved phase before evaluating the next phase.

The engine also uses the shared five-lane policy and runs cache first for background analysis.

Remaining work: the foreground runtime must persist and advance the fractional clock position after every resolved player action; the current pipeline state stores progress but does not yet drive all action-time transitions.

### I and J. Shared five-lane policy and cache carryover — partially implemented

The single core set is:

```text
cache
rules
character
special
create
```

It is used by the Specialist Registry, Turn Router, Coverage Check, Specialist Runner, and Phase Tick Engine.

Cache runs first in the Specialist Runner and background tick engine. A malformed/non-complete cache blocks subsequent specialist work. Lead Resolver deterministically carries the Cache Specialist's delta into its resolution record. Recorder reads that nested normal resolution output and persists readable cache-delta records in `TEMP_MEMORY.md`.

Remaining work:

- Admin Agent still has its explicit `no_specialists` test/admin bypass. It must be restricted so it cannot service gameplay-resolution work.
- A complete merge/expiry policy for the consolidated `## Game Cache` section has not yet been implemented; individual recorded deltas round-trip, but compaction is still needed.

### K. Visibility controls — partially implemented

`backend/visibility_filter.py` is fail-closed for background records: an entry needs both an explicitly OOC-safe label and a roleplay-visible label before it reaches narrator-facing background data.

`Narrator.player_input()` now constructs a reduced allow-list projection instead of receiving the complete Lead Resolver output. Internal notes, specialist results, model metadata, cache state, and private background details are excluded.

Remaining work: Lead Resolver outcome text itself is still trusted as player-safe. Before live play, resolution output needs a stricter field-level visibility contract so a private fact cannot be embedded in a free-text `outcome` string.

### L and M. Runtime day-end/world-event gates — implemented skeleton

`brain/runtime_state.py` persists private resumable state in:

```text
brain/state/session_runtime.json
```

It tracks setup status, play gate, position/progress, pending dice, pending clarification, day-end review, editor receipt, and pending world event.

`pipeline.py` currently supports these gated transitions:

```text
setup draft
→ applied setup
→ world-event pending
→ open play

day-end review
→ approved editor receipt
→ world-event pending
→ open play
```

It can save a d100 and requires a selected trigger, encounter condition, and latest phase before opening next-day play.

`trial/30_run_runtime_lifecycle_dummy.py` verifies setup, day-end, receipt, saved-roll, and resume gate behavior.

Remaining work: the pipeline does not yet invoke the World Specialist itself, generate/persist the d100 through a dice service, enforce encounter conditions/deadlines against live player movement, or produce the combined day-end Admin proposal automatically.

### N. Setup and resume — implemented skeleton

The private runtime store and pipeline expose setup-state and resume-state methods. Resume invokes Admin Editor transaction recovery before returning the saved stage.

Remaining work: no complete terminal/UI flow currently drafts characters, chooses a main character, assembles starting Markdown documents, obtains player approval, and schedules an opening scene. The methods are state gates, not a finished guided setup experience.

## 2. Current architecture

```text
Player turn (not fully orchestrated yet)
  → Turn Router
  → Evidence Bundle
  → Cache Specialist
  → Rules / Character / Special / Create
  → Coverage Check
  → Lead Resolver
  → Narrator safe projection
  → Recorder

Private runtime state
  brain/state/session_runtime.json
  brain/state/background_state.json
  brain/state/model_calls.jsonl
  brain/state/editor_transactions/
  brain/state/editor_receipts/

Player-readable OOC state
  markdown_files/Experimentation Register.md
  markdown_files/TEMP_MEMORY.md

Approved canon/template edits
  Admin Agent → version binding → player approval
  → transactional Admin Editor → receipt
```

## 3. Remaining blocking work for a finished pipeline

### 1. Full foreground orchestrator

`pipeline.py` must actually execute and persist this complete continuation loop:

```text
route
→ build evidence
→ run specialists
→ coverage/gap path
→ resolve
→ await saved dice or clarification when required
→ safe narration
→ record
→ update phase/background state
→ return resumable checkpoint
```

### 2. Day-end proposal integration

The runtime must turn Recorder's readable day-end promotion proposal into one bound Admin Agent proposal, run dependent recalculation, require player approval, apply through Admin Editor, save the receipt, refresh indexes, then schedule the next-day world event.

### 3. World Specialist scheduler

The scheduler must invoke World independently of branch unlock routing at new-day time, validate the 1–100 pool, save exactly one d100, store the pending event privately, and enforce encounter condition/latest phase during subsequent play.

### 4. Terminal/UI setup and resume

A terminal or UI must render the runtime state, ask saved dice/clarification questions again after restart, block play at non-open gates, and implement guided character/party/start-document setup.

### 5. Failure-path regression suite

Add dedicated tests for:

- editor failure on each target replacement and audit append;
- crash/restart before and after each receipt;
- stale-source proposal rejection;
- duplicate proposal retry;
- cache compaction/expiration;
- multi-phase blocked ordering;
- private fact leakage in narration, logs, and OOC mirror;
- world-event deadline and no-reroll behavior.

### 6. Operational details

- The default Turn Router still requires Git unless created with `require_git=False`; the final pipeline must set or expose this configuration deliberately.
- Evidence indexes should be refreshed after approved edits and Recorder/background writes by the finished orchestrator.
- Private state is listed in `.gitignore`; no private runtime journal should be committed.

## 4. Validation completed

Offline deterministic tests currently passing:

```text
trial/23_run_dummy_specialists.py
trial/24_run_recorder_dummy.py
trial/25_run_backend_dummy.py
trial/26_run_admin_dummy.py
trial/27_run_branch_unlock_dummy.py
trial/28_run_incremental_evidence_index_dummy.py
trial/29_run_model_gateway_dummy.py
trial/30_run_runtime_lifecycle_dummy.py
```

These validate local contracts and selected persistence behavior. They do not certify live provider quality, terminal interaction, full crash recovery, or end-to-end gameplay.

## Core conclusion

The project now has much of the safety infrastructure that the earlier audit found missing. The remaining central task is not another specialist or another storage template:

> Build the actual foreground orchestration loop in `pipeline.py`, then connect it to the already implemented transaction, runtime-state, cache, visibility, Recorder, day-end, and world-event seams.
