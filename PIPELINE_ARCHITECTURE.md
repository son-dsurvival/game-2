# Game Pipeline Architecture

This document defines how the game moves an input through routing, evidence,
specialists, resolution, narration, persistence, and resumable state.

## 1. Entry points

```text
Terminal:  pipeline.py
Web UI:    web_frontend.py
```

Both interfaces send input to the same `CampaignPipeline` in
`brain/game_runtime.py`. The interfaces do not resolve game actions or write
campaign Markdown directly.

```text
process_input()
  -> _process_input()
  -> CampaignPipeline command or submit method
```

## 2. Input dispatch

Every input is classified before it can affect the campaign:

```text
command (/...)
  -> command-specific CampaignPipeline method

{...}
  -> OOC administrative operation

answer while awaiting_clarification
  -> saved operation continuation

ordinary text while open
  -> in-world Player Turn
```

An OOC clarification resumes the existing operation. It is never routed as a
new in-world action.

## 3. Foreground Player Turn

```text
open
  -> CampaignPipeline.submit
  -> Turn Router
  -> Evidence Bundle Builder
  -> scoped Specialists
  -> Coverage Check
  -> Lead Resolver
  -> Narrator
  -> Recorder
  -> phase/background processing
  -> checkpoint
  -> open or another saved gate
```

### Call and data flow

| Stage | Implementation | Receives | Sends |
|---|---|---|---|
| Route | `GameModules.route` → `TurnRouter` | Player message, runtime state | Mode, segments, tags, required specialists |
| Evidence | `GameModules.evidence` → `EvidenceBundleBuilder` | Route, state, history | Frozen Evidence Bundle |
| Specialists | `GameModules.specialists` → `SpecialistRunner` | Frozen bundle, selected specialist names | Specialist findings and citations |
| Coverage | `CoverageCheck` | Specialist results | Ready, blocked, missing, or malformed coverage status |
| Resolve | `GameModules.resolve` → `LeadResolver` | Bundle, findings, state, dice if saved | Authoritative resolution record |
| Narrate | `GameModules.narrate` → `Narrator` | Player-safe resolution | Player-facing narration |
| Record | `GameModules.record` → `SessionRecorder` | Resolution and final position | Pending session record in `TEMP_MEMORY.md` |
| Background | `GameModules.background` → `PhaseTickEngine` | Entered phases, foreground result | Private backend tick results |
| Checkpoint | `RuntimeStateStore` | Operation results | Durable resumable runtime state |

The Lead Resolver is the only component that decides legality, success,
failure, costs, time, consequences, relationship changes, or branch changes.

## 4. Clarification and dice paths

### Missing evidence

```text
Coverage or Lead Resolver detects a gap
  -> identify missing fact/rule/calculation
  -> ask player, or request authorized assumption
  -> save operation and clarification link
  -> awaiting_clarification
  -> player answer
  -> restore same operation
  -> rebuild affected evidence
  -> rerun affected stages
```

### Dice

```text
Lead Resolver requests dice
  -> DiceJournal generates and saves result
  -> awaiting_dice
  -> saved operation resumes
  -> Lead Resolver receives the same roll
```

A retry must never generate a second roll for the same request.

## 5. OOC administrative pipeline

```text
{request}
  -> Turn Router
  -> Evidence Bundle Builder
  -> scoped Specialists
  -> Coverage Check
  -> Admin Agent
       -> direct answer
       -> clarification
       -> edit proposal
  -> Player Language Agent when player-facing conversion is needed
  -> player review/revision
  -> explicit approval
  -> Approval validation
  -> Admin Editor
  -> audit receipt
  -> evidence-index refresh
  -> previous runtime gate
```

`Admin Agent` is read-only. Only `outside game/admin_editor.py` applies approved
Markdown changes.

## 6. Command pipeline

The terminal and web layers dispatch commands to `CampaignPipeline`:

| Command | Pipeline responsibility |
|---|---|
| `/new-game` | Reset/setup draft and begin new-game flow |
| `/new-character` | Draft an additional player character |
| `/new-party-member` | Draft an autonomous party member |
| `/add` | Add another setup character |
| `/main NAME` | Select the main character |
| `/review` | Prepare or redisplay a proposal |
| `/next-file` | Review the next proposal file |
| `/approve` | Apply an approved proposal |
| `/approve-reset` | Confirm campaign replacement |
| `/cancel-setup` | Discard setup draft without changing the active campaign |
| `/undo` | Undo setup input |
| `/cancel-operation` | Cancel an unapplied operation |
| `/end-day` | Prepare day-end review |
| `/resume` | Resume from a valid pending gate |
| `/retry` | Retry the latest safe failed stage |
| `/specialists` | List stored specialist proposals |
| `/install NAME` | Prepare specialist installation |

Commands create or continue durable operations. They do not bypass evidence,
approval, or persistence gates.

## 7. New-game setup

```text
setup_required
  -> character/party draft
  -> main-character selection
  -> sequential setup batches
  -> specialist analysis
  -> proposal preview
  -> player review/revision
  -> approval
  -> Admin Editor transaction
  -> setup activation
  -> new_game_pending
  -> {resume}
  -> open
```

Setup batches are handled by `brain/setup_batches.py` and the setup draft helper
in `outside game/setup_drafts.py`. Character-scoped specialists are created by
`brain/specialists/character_group.py`.

No starting option, modifier, class, skill, spell, or resource is silently
selected or permanently written before approval.

## 8. Phase and private backend pipeline

When the Lead Resolver confirms crossed phase boundaries:

```text
foreground time change
  -> PhaseClock
  -> one transition per entered phase
  -> PhaseTickEngine
  -> AutonomyResolver
  -> selected backend specialists
  -> BackendLeadResolver
  -> private BackgroundStateStore commit
  -> queue resolved world-entity changes
  -> VisibilityFilter
  -> safe OOC/player interruption only when explicitly visible
```

Phase ticks handle chronological autonomy and private actor actions. World
population growth and recurring resource formulas are planned and committed
once in the approved day-end batch rather than on every turn. Backend work is
chronological and idempotent by `tick_id`. An unresolved phase blocks
dependent later phases and remains retryable.

Backend components:

- `backend/phase_clock.py` — phase arithmetic;
- `backend/phase_tick.py` — sequential tick orchestration;
- `backend/autonomy_resolver.py` — attempted off-screen actor actions;
- `backend/backend_lead_resolver.py` — private decision boundary;
- `backend/background_state.py` — private directives, ticks, and surprises;
- `backend/visibility_filter.py` — fail-closed visibility projection;
- `backend/world_director.py` — private world-process planning.

The backend does not call the Narrator for hidden work.

## 9. Day-end and next-day event pipeline

```text
/end-day or completed-day boundary
  -> chronological pending phase work
  -> collect TEMP_MEMORY and backend results
  -> WorldDirector.plan_day
  -> recurring process/resource specialist
  -> BackendLeadResolver process validation
  -> world/branch/resource/modifier review
  -> combined Admin Agent proposal
  -> player questions/revisions
  -> explicit approval
  -> Admin Editor transaction
  -> WorldDirector.commit_day
  -> reconcile working records
  -> refresh indexes
  -> save exactly one d100
  -> World Specialist prepares pending event
  -> new_day_pending
  -> {resume}
  -> open
```

The next-day event remains pending until its encounter condition is met. Its
latest phase is enforced. The event is not silently skipped by sleep or travel.

## 10. Persistent stores

| Store | Role |
|---|---|
| `brain/state/session_runtime.json` | Current operation, gate, position, draft, dice, and pending event |
| `brain/state/session_runtime_events.jsonl` | Append-only execution journal |
| `brain/state/player_prompt_history.txt` | Player-facing prompt/result transcript |
| `brain/state/model_calls.jsonl` | Model requests, results, errors, and reuse metadata |
| `brain/state/background_state.json` | Private backend directives, ticks, and surprises |
| `brain/state/world_state.json` | Private world entities, queued entity changes, growth, and scheduled events |
| `brain/state/recurring_processes.json` | Private recurring process schedules and history |
| `brain/state/resource_formulas.json` | Private deterministic recurring-process formulas |
| `markdown_files/TEMP_MEMORY.md` | Player-known working records awaiting promotion |
| `markdown_files/` campaign documents | Approved persistent campaign state |
| `brain/state/editor_receipts/` | Applied administrative transaction receipts |
| `brain/info/evidence_index.json` | Searchable evidence index |
| `brain/info/canon_section_index.json` | Exact Markdown section targets |

## 11. Safety invariants

1. Specialists advise; the Lead Resolver decides.
2. The Evidence Bundle gathers evidence but does not judge sufficiency.
3. The Narrator cannot change a resolved result.
4. The Recorder does not promote permanent canon directly.
5. Admin Agent proposes; Admin Editor applies approved Markdown only.
6. Clarifications resume saved operations rather than creating new turns.
7. Dice are generated once and reused on retry/resume.
8. Private backend facts are excluded from narration and player-facing records.
9. Branch candidates and unlocks require evidence and the normal persistence gate.
10. Every stage is checkpointed so failures can resume safely.
11. A completed operation returns to `open` only when no pending gate remains.
