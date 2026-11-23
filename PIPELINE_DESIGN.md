# Game Pipeline Design

## Status and scope

This document records the decisions agreed with the player during the design interview. It is the intended behavior, **not a claim that the runtime already implements it**. See `PIPELINE_IMPLEMENTATION_AUDIT.md` for the current script interfaces, verified gaps, and implementation order.

Initial delivery: a terminal chat backed by reusable Python orchestration. `pipeline.py` is the entry point; terminal input/output must remain separate from game orchestration so another interface can be added later. Reuse the existing brain, backend, and outside-game scripts rather than replacing their responsibilities.

There is one campaign in `markdown_files/`. Multiple campaign slots and a web interface are out of scope for now. The world lore is player-maintained; do not generate or overwrite it as part of this implementation.

## 1. Core rules and ownership

- Rules and established world lore constrain character creation, player answers, revisions, and outcomes.
- Player-provided facts are accepted unless they conflict with rules or established lore. The Lead Resolver may ask about **any** missing information, not only player intent. Explain conflicts and ask for a valid revision rather than silently overriding the player.
- The Lead Resolver decides outcomes. Specialists advise; the Narrator expresses resolved facts; the Recorder persists working state.
- The Game Cache Specialist is mandatory and runs before every other specialist in **all** flows.
- Code generates dice results and persists them before use. Models must not invent rolls. Resuming or retrying uses the existing roll.
- Permanent campaign document changes require explicit player approval and are applied through `outside game/admin_editor.py`.
- Resolved player-known working state, hidden backend working state, execution checkpoints, and technical prompt history may be saved automatically. These writes are not permanent campaign promotion.
- Administrative questions do not change campaign state or advance game time. Recording their technical prompt/result history is still allowed.
- Hidden information must not leak through narration, working-memory review, admin answers, logs, errors, or cached responses.

## 2. State and storage responsibilities

| State | Purpose | Writer and approval |
| --- | --- | --- |
| Rules and world lore | Established references | Preserve during reset; changes require approval |
| Permanent campaign Markdown | Approved characters, resources, relationships, experiments, branch state, event/game logs | Admin Editor, approved proposal only |
| `markdown_files/TEMP_MEMORY.md` | Player-known current session records pending promotion | Recorder automatically; reviewed at day-end |
| Private backend working storage | Hidden actions, world state, NPC state, schedules, pending unrevealed events | Backend automatically; excluded from player-facing documents |
| Execution journal | Stage progress, identities, state versions, saved dice, pending questions/approvals, commit receipts | Orchestration automatically |
| Prompt/result history and reuse cache | All model requests/results, plus safe reuse metadata | Model-call implementation automatically |
| Character drafts | Proposed new party before campaign replacement | Setup flow; not active campaign state |

These stores have different roles. In particular, the prompt cache is **not** the authoritative source of campaign facts, and compact Game Cache Specialist context is **not** a substitute for full prompt/result history. Private backend state must remain durable even if it cannot be reconstructed from player-visible documents.

Private storage means excluded from player-facing game interfaces and document review. It is not a promise to conceal local files from the person who owns the computer.

### Reset behavior

Keep the old campaign and its cache intact while creating the new party. Only after final party approval and explicit replacement confirmation:

1. Stage all new campaign documents and working state.
2. Preserve rules, world lore, and reference/template structure; reset campaign-specific records.
3. Replace campaign state as one recoverable operation.
4. Delete the **old campaign's** prompt/result cache, not archive it. Preserve prompt history belonging to the newly approved setup.
5. Activate the new campaign identity and refresh derived indexes.

Cancellation or a failed replacement leaves the old campaign usable. Reset must be targeted: lore and campaign event/game logs can share a file, so deleting a whole world document is not acceptable.

## 3. New-game flow

Repeat the guided questions for each starting character:

1. **Identity:** name, age, race.
2. **Stats:** allocate 30 points across AGI, INT, STR, END, WIS, PRE.
3. **Description:** character description, background, personality.
4. **Class:** player concept, player-specified mechanics, AI-created class, or a combination. Validate against the rules.

Extreme stat allocations, including zero, are permitted. Use the existing **stat < 3** penalties, not a new < 5 threshold. Derive HP and other values from the rules; do not silently rebalance a weak build. Do not invent additional numeric limits that have not been established by the rules or the player.

Derive starting equipment, money, skills, relationships, status-sheet entries, and other starting records from the character/background under the rules. These are proposals, not saved facts yet.

The player can create several characters, reviews the whole party and all derived details, and may revise them. Recalculate affected derived values after changes. The player selects one main character; the others act autonomously unless instructed.

After final approval and reset confirmation:

```text
Approved party
  -> Admin Editor fills/replaces the relevant campaign documents
  -> successful save and state activation
  -> opening scenario designed from character background and world lore
  -> player-facing opening and working-state recording
```

Do not begin the opening scenario before approved starting documents are successfully stored. Use cache-first specialist analysis during setup/scenario preparation as well.

## 4. During-game flow

```text
Player input
  -> wait for prior required backend work
  -> Turn Router
  -> Evidence Bundle
  -> Game Cache Specialist
  -> remaining mandatory/routed specialists
  -> Lead Resolver
       -> missing evidence: expand evidence and rerun affected analysis
       -> needs clarification: ask player, persist suspension, resume same turn
       -> awaiting dice: generate/save requested roll, resume same resolution
       -> resolved: continue
  -> Narrator
  -> Recorder
```

The other core lanes are rules, character, special, and create; include additional specialists when needed. Every later specialist receives the latest Game Cache Specialist context. Required analysis failures must not be treated as successful resolution.

Clarification answers can address any missing fact. Keep the same logical turn, retain saved rolls, refresh affected evidence/context, and accept answers only when consistent with rules/lore. Do not narrate an unresolved action as completed.

### Parallel hidden backend

The backend is a parallel runtime track, **not** a fixed serial step after the Recorder:

```text
Lead Resolver confirms elapsed time / crossed phases
  +-> Narrator -> Recorder
  +-> hidden phase work, processed chronologically -> private working-state commit
```

- Trigger backend advancement only at confirmed game-time phase boundaries, not every message or elapsed wall-clock time.
- The backend can overlap remaining foreground work, but both tracks use explicit state versions and coordinated commits. No last-writer-wins updates to shared resources.
- Do not require the Recorder to finish before every backend calculation; instead make the resolved foreground state available as a versioned input and serialize conflicting commits.
- Accept the next player input while backend work is running, but do not resolve it until relevant prior work finishes successfully.
- A failed or unresolved phase blocks dependent later phases; never advance through it as though it succeeded.
- Hidden results stay private. When a fact becomes player-known, project it into normal narration/working-memory/approval processing at the appropriate encounter.

### NPC autonomy and rest

Explicit orders and schedules take priority. AI decisions fill gaps using character state, circumstances, and rules. Sleeping NPCs rest rather than perform normal activities; the rest of the world can still progress.

Track fractional phase progress supported by the rules. Short naps use normal rest processing; they do not automatically end the day.

When the player explicitly sleeps until tomorrow or ends the day, advance through remaining phases chronologically and run applicable background activity. Do not award a full night's rest upfront. Danger can interrupt sleep: grant only earned rest, stop automatic advancement, suspend day-end completion, and return control when the player must respond.

## 5. Outside-game flow

Requests wrapped in `{...}` use the administrative flow:

```text
Turn Router -> Evidence Bundle -> Game Cache Specialist
  -> other specialists -> Admin Agent
       +-> read-only answer / clarification
       +-> rule-compliant exact edit proposal
             -> player review/revision
             -> explicit approval of final version
             -> Admin Editor
             -> reconcile working state and refresh indexes/cache versions
```

The Admin Agent is read-only. No document edits are applied because the agent merely suggested them. Questions and explanations return without changing campaign state.

Approved mid-day edits apply immediately while gameplay is paused, rather than waiting for day-end. Reconcile pending working records so a later turn or day-end promotion cannot overwrite the approved change with stale information.

An approval applies only to the exact reviewed proposal. Revising proposed content invalidates the previous approval. Proposed instructions for brain/backend behavior are not automatic permission to execute arbitrary code.

## 6. End-of-day flow

Triggers:

- The player passes the **Midnight** phase into the next day.
- The player explicitly chooses to sleep until tomorrow/end the day, subject to chronological advancement and interruptions above.

Use game time, not the computer clock or application exit. If one action spans several days, do not skip the intervening review gates or unresolved phases.

```text
Finish applicable chronological phase work
  -> finalize player-known TEMP_MEMORY for the completed day
  -> cache-first specialist analysis
  -> Admin Agent prepares promotion/review
  -> World Specialist prepares completed-day event-log updates
  -> prepare player-visible daily prompt/result game-log entries
  -> one combined review of ALL permanent changes
       <-> player queries, corrections, revisions
       <-> rule/lore checks and dependent consequence recalculation
  -> explicit approval of the final proposal
  -> Admin Editor applies the whole approved proposal
  -> reconcile working state / mark promoted records / refresh indexes
  -> saved d100 + World Specialist prepare the next-day event
  -> next day becomes playable when required preparation succeeds
```

The World Specialist's event-log update is prepared **before final approval** to avoid a second review. The original suggestion to generate an unreviewed permanent event-log change after approval was superseded.

Gameplay is blocked until approval **and** successful application. The player may query and revise the proposal, including changing resolved outcomes, provided revisions obey rules and established lore. Recalculate dependent outcomes and resources, reuse existing saved dice where applicable, and present the revised proposal for approval again. Preserve the original technical prompt history and mark superseded results rather than pretending the original calls never happened.

Declining or postponing approval does not start the next day. An editor failure also keeps the gate closed. Administrative review and restart/resume remain available.

### Next-day world event

After approved day-end application, code rolls and saves the required d100. The World Specialist uses the rules' trigger/pool and the supplied roll to design a next-day event. It must provide:

- an event identity and target day;
- setup/circumstances consistent with current rules and lore;
- the encounter condition;
- a latest phase for encountering it;
- a pending status, not a pre-resolved player outcome.

The event must be encountered during that next day, but need not be its first scene. The in-game pipeline introduces it when its condition is met and enforces its latest-phase deadline. Sleep/time skipping must not silently bypass it.

Send the event to the Lead Resolver as pending context; resolve consequences at encounter time using current state and player choices, then continue through Narrator and Recorder. Unrevealed event setup stays private and does not bypass approval to enter permanent player-readable logs.

### Event log versus game log

- **Event log:** approved world-event developments and established world-state changes.
- **Game log:** that day's approved, player-visible prompt/result history supplied from the cache to the Admin Editor.

Do not conflate these. A short narrative turn summary alone does not fulfill the requested prompt/result history. Exclude hidden backend entries and hidden content embedded in otherwise visible-track prompts. Preserve full raw history privately; only explicitly safe content reaches player review and the permanent game log.

## 7. Game Cache Specialist

Mandatory in setup, gameplay, administrative requests, backend phases, and day-end analysis. Runs **before** all other specialists, even where those later specialists run concurrently.

Reviews:

- conversation history and previous compact context;
- active threads and commitments;
- unresolved questions;
- pending event conditions;
- expiring facts and changes to their validity.

Returns current, bounded advisory context to subsequent specialists. It never resolves outcomes, changes canon, or writes permanent documents. Context must distinguish established facts, player claims, proposals, expired facts, and unresolved items.

Persist its context via the appropriate working-state writer. Keep private and player-visible contexts separated. Its version is part of result-reuse matching so old context cannot silently supply an old result.

## 8. Persistent prompt/result cache

Capture model calls across every flow, including routing, evidence extraction/selection, cache and other specialists, gap analysis, Lead Resolver, Narrator, Recorder, Admin Agent, and world-event preparation. Record repair attempts and failures as attempts too. Include player interaction/clarification history and stage lineage so a daily game log can be assembled.

Each model-call entry includes:

- campaign identity, day/phase, turn or operation identity, stage, and call/attempt identity;
- exact request messages/prompt and relevant generation settings;
- provider/model identity and prompt/contract version;
- relevant evidence, state, conversation, and Game Cache context versions/hashes;
- raw response, validated result where available, validation/error status;
- visibility classification and provenance;
- reuse linkage when a prior successful result is reused.

Never store API keys or authorization headers. Apply secret exclusion to request/error logging, not just successful responses.

### Reuse policy

Reuse only a successful, validated result for an identical request with matching relevant state, evidence/context, model settings, visibility scope, and campaign identity. Resume may reuse a completed stage. Similar wording is insufficient. Failures and incomplete responses are retained for diagnosis but never reused as successful results.

A cache hit must not replay resource changes, document writes, dice, or backend commits. Side effects have separate durable operation identities and commit receipts. Context revisions, approved edits, changed rules/lore, and new campaign initialization invalidate affected reuse.

Store results durably before advancing the next stage. This reduces repeated calls but cannot guarantee exactly one provider invocation if a network/process failure occurs after the provider completes and before the local response is saved. Exactly-once **local effects and dice consumption**, rather than an impossible blanket guarantee about remote calls, are the required recovery property.

## 9. Recovery and approved-edit transactions

Persist enough progress to resume the last unfinished step after exit or failure, including character drafts, clarification questions, pending approvals, saved rolls, phase cursors, and next-day event preparation.

Admin Editor operations must be all-or-nothing across their full document set:

1. Bind approval to exact proposed content and expected source versions.
2. Prepare and validate the complete updated content for each file, composing multiple edits to the same file.
3. Stage a recoverable transaction before changing live files.
4. Coordinate readers/writers so partial updates cannot be used as live game state.
5. Commit all approved changes, or restore the prior versions and retain the approved proposal for retry.
6. Persist an application receipt and reconcile pending records without applying the changes again after restart.

A filesystem rename is atomic for one file, not an entire multi-document proposal. Recovery must handle a crash during application, including successful document writes followed by a failed audit/checkpoint write. Stale proposals require revalidation and, if content changes, renewed approval.

## 10. Formal state model

Every request is represented by a durable operation envelope:

```text
operation_id
operation_kind       setup | gameplay | query | administration | day_end | command
stage                current internal stage
play_gate             player-visible gate
revision              proposal/clarification revision
state_version        source runtime version
source_versions      hashes of Markdown files read by a proposal
snapshot             recoverable pre-stage state
saved_dice           rolls already consumed by this operation
clarification_links  questions and their answers
receipt              committed side-effect receipt, when applicable
```

The operation journal is authoritative for recovery. A model response, prompt cache entry, or Markdown proposal is never sufficient by itself to resume or commit an operation.

### Player-visible gates

| Gate | Meaning | Allowed continuation |
| --- | --- | --- |
| `setup_draft` | New characters and derived records are still being drafted | Draft input, `/main`, `/review`, `/cancel-setup`, `/quit` |
| `setup_review` | One setup batch is proposed and has not been applied | Query, revise, `/approve`, `/approve-reset`, `/back-setup`, `/quit` |
| `action_running` | A gameplay operation is executing | Wait; no competing resolution |
| `awaiting_clarification` | The same operation needs a player answer | Answer the question; the operation resumes |
| `awaiting_dice` | Code must generate or receive a required roll | Roll once and resume the same operation |
| `admin_review` | A non-reset permanent edit is proposed | Query, revise, `/approve`, `/quit` |
| `day_end_pending` | Chronological end-of-day work is incomplete | `/review`, `/quit` |
| `day_end_review` | Combined day-end changes await approval | Query, revise, `/approve`, `/quit` |
| `applying` | An approved transaction is being committed | Wait; recovery handles interruption |
| `world_event_pending` | The next-day event is prepared but play cannot start yet | Complete event preparation or `/retry` |
| `paused` | Play is intentionally suspended | `/resume`, read-only commands, `/quit` |
| `retry` | A stage failed and has a saved pre-stage snapshot | `/retry`, `/status`, `/quit` |
| `open` | The campaign can accept normal gameplay input | Gameplay action, query, command |

### State transitions

```text
setup_draft
  -- /review ----------------------> setup_review
  -- /cancel-setup ----------------> prior active campaign gate
  -- /quit ------------------------> setup_draft (persisted)

setup_review
  -- player revision --------------> setup_review (new revision)
  -- /back-setup ------------------> setup_review (previous approved batch)
  -- /approve ---------------------> applying (normal batch)
  -- /approve-reset ---------------> applying (final replacement)
  -- /cancel-setup ----------------> prior active campaign gate

open
  -- gameplay action --------------> action_running
  -- player query -----------------> query_running
  -- administrative request -------> admin_review or awaiting_clarification
  -- end-of-day trigger -----------> day_end_pending
  -- /pause -----------------------> paused

action_running
  -- missing information ----------> awaiting_clarification
  -- required roll ----------------> awaiting_dice
  -- unresolved evidence ----------> action_running (gap expansion)
  -- resolved ---------------------> narration

narration
  -- safe narration emitted -------> recording
recording
  -- working record committed ----> open or day_end_pending
  -- required background work -----> background_pending

admin_review / day_end_review
  -- player revision --------------> same gate (new revision)
  -- approval ---------------------> applying
  -- stale source -----------------> same gate with regenerated proposal

applying
  -- transaction committed --------> reconcile
reconcile
  -- derived state refreshed ------> open, world_event_pending, or next setup batch
  -- failure ----------------------> retry (with pre-stage snapshot and receipt)

retry
  -- /retry -----------------------> failed stage from its saved pre-stage snapshot
```

No transition may silently skip a gate, consume time, consume a die, or apply a permanent file change. A failed transition leaves the last committed state usable.

## 11. Action and query pipelines

All in-game actions use one orchestration contract. The action-specific specialists vary, but the state and safety rules do not.

### Gameplay actions

The supported action kinds are:

- dialogue, persuasion, negotiation, and social interaction;
- movement, exploration, investigation, and travel;
- experiments, research, study, and analysis;
- combat, pursuit, defense, and hazards;
- crafting, construction, repair, and resource use;
- training, active-skill use, spell use, and effect application;
- rest, sleep, waiting, and day-ending actions;
- relationship decisions and party instructions.

Each follows:

```text
player action
  -> classify action and intent
  -> gather rules, lore, character, world, and current-state evidence
  -> Game Cache Specialist (mandatory first specialist)
  -> required/routed specialists
  -> coverage and contradiction check
  -> Lead Resolver
       -> clarification: await answer, then resume this operation
       -> dice: save one roll, then resume this operation
       -> insufficient evidence: expand evidence and rerun affected stages
       -> resolved outcome
  -> safe Narrator projection
  -> Recorder working-state commit
  -> phase/background advancement when warranted
  -> open or day-end gate
```

A player action may update private working state and `TEMP_MEMORY.md` through the Recorder, but it does not directly edit permanent canon. A permanent consequence becomes a reviewed proposal through the administrative or day-end flow.

### Questions, queries, and corrections

A query is read-only unless the player explicitly requests a change:

```text
query
  -> classify requested fact
  -> gather relevant rules/lore/current state
  -> fact-check and identify conflicts
  -> show answer with source locations and uncertainty
  -> return to the prior gate without advancing time
```

If the player and agent identify a needed correction, the query creates a proposal; it does not apply the correction. The proposal must identify the affected file/section, old value, new value, reason, dependencies, and required approval. Questions about a pending proposal are read-only. A clarification is different: it blocks an unfinished operation and, once answered, resumes that same operation.

### Status, modifier, skill, and spell creation

Creation is a staged proposal, not an immediate grant:

```text
request creation
  -> gather character history, rules, evidence, and existing records
  -> generate rule-valid options
  -> show options and trade-offs
  -> player selects an option
  -> player confirms the exact option
  -> recalculate dependent values
  -> propose the affected status/ledger/relationship records
  -> approval boundary for permanent records
  -> apply and refresh derived indexes
```

For a new campaign, active skills, spells, effect modifiers, stat modifiers, and class modifiers may be generated as starting options. During an active campaign, existing records are shown first and any new or changed capability requires an explicit proposal. Selection alone is not approval, and a query must not be interpreted as consent.

### Character and relationship creation

Character creation orchestrates, but does not duplicate, the status and relationship workflows:

```text
character input/evidence
  -> identity, history, stats, and class proposal
  -> status creation
  -> relationship creation
  -> relevant modifier/skill/spell creation
  -> specialist group proposal
  -> complete character review
  -> approval and storage
```

Player-character relationships use the player's supplied background and explicit choices. Non-player relationships may include voice, mannerisms, personality, decision thresholds, autonomy, relationship scores, and bond behavior, but generated assumptions must be labelled as assumptions and reviewed before becoming established facts.

### Ledger and branch administration

Ledger updates and specialist/branch unlocks use the same proposal contract. A branch is first recorded as a candidate, then validated against established evidence, then proposed with its rules, specialist scope, target file, and dependencies. Discovery does not equal unlock. Unlocking a branch requires player approval and a successful write; a failed or declined proposal leaves the branch inactive.

## 12. Approval boundaries

Approval is bound to the exact proposal digest and source-file hashes. Any revision, source change, dependent recalculation, or changed player answer invalidates the previous approval.

| Operation | Automatic writes allowed | Required player boundary |
| --- | --- | --- |
| Model calls, journal checkpoints, private cache, saved clarification, saved dice | Private runtime only | None |
| New-character draft and derived previews | Draft storage only | Player review before promotion |
| Gameplay narration and `TEMP_MEMORY.md` working records | Recorder-controlled working records | No permanent approval; hidden data remains private |
| Status, relationship, ledger, skill, spell, modifier, or class changes | Proposal only | Exact selection/confirmation, then proposal approval |
| Normal administrative edit | Proposal only | `/approve` |
| Day-end event/game-log and world-state promotion | Proposal only | Combined day-end review and `/approve` |
| Specialist or branch unlock | Candidate registry only | Explicit proposal review and `/approve` |
| Replacement of the active campaign | Staged replacement only | `/approve-reset` |
| Read-only commands and queries | Journal/query history only | None; they do not advance time |

`/approve` must never be accepted as a reset confirmation. `/approve-reset` is required when the operation replaces the current campaign. Approval of one batch does not approve later batches or future revisions.

## 13. Rollback, retry, and recovery

### Before commit

- Do not mutate permanent Markdown while a proposal is being generated or reviewed.
- Save a pre-stage snapshot before every side-effecting stage.
- Keep proposal revisions immutable; mark superseded revisions rather than editing them in place.
- Revalidate source hashes and the proposal digest immediately before applying.

### During commit

The Admin Editor stages every updated file and validates the complete multi-file result before replacing live files. It records the transaction identity, original hashes, updated hashes, proposal digest, and operation identity. A failure restores all files that were replaced and leaves the gate at `retry` or the review gate with the exact proposal still available.

A successful file replacement followed by a checkpoint failure is recovered using the transaction receipt. Recovery must not apply the same document change twice. Dice, resource costs, Recorder entries, background ticks, and other local effects use separate durable receipts and are likewise committed at most once locally.

### After failure or cancellation

- `/retry` resumes from the saved pre-stage snapshot, not from a partially mutated in-memory object.
- A missing snapshot is a hard recovery error; do not guess or rebuild state from model output.
- Cancellation of setup discards only the draft and staged transaction. It preserves the active campaign.
- A failed reset preserves the old campaign and keeps the new staged campaign recoverable or discardable.
- A failed background phase blocks dependent later phases; it cannot be treated as successful.
- A failed narrator or output step may reuse the committed resolution, but must not reroll dice or reapply resource effects.
- A failed permanent write cannot advance the play gate or clear the pending proposal.

## 14. File ownership and write rules

Markdown files are the source of truth for approved player-visible campaign facts. Each workflow may read broadly for context, but may write only through an approved Admin Editor proposal targeting its owned sections.

| File | Owner | Write rule |
| --- | --- | --- |
| `markdown_files/game rules (1).md` | Player/rules administration | Read-only to gameplay; changes require explicit rules-edit proposal and approval |
| `markdown_files/TERMS_AND_NOMENCLATURE.md` | Domain administration | Changes require terminology proposal and approval; dependent references must be checked |
| `markdown_files/🌍 CORE WORLD FRAME (REFINED).md` | World administration/player | Lore is preserved; Event Log and Game Log updates require reviewed proposals; never replace the whole file blindly |
| `markdown_files/status sheet.md` | Status/character workflow | Owns approved character identity, stats, class, status, and derived capability sections |
| `markdown_files/character relationship.md` | Relationship workflow | Owns approved party and non-party relationship records, autonomy, scores, and bond behavior |
| `markdown_files/Ledger Resources.md` | Ledger workflow | Owns approved inventory, resource, equipment, and ledger sections; quantities require evidence |
| `markdown_files/Experimentation Register.md` | Experiment/background workflow | Receives only explicitly player-visible or approved teammate/background records; private backend state never belongs here |
| `markdown_files/TEMP_MEMORY.md` | Recorder/day-end workflow | Working player-known records only; promotion is reviewed; it is not the complete private backend state |
| `markdown_files/Branch Registry.md` | Branch administration | Candidate and unlocked branch records only; candidates do not activate specialists |
| Evidence indexes and descriptions | Index builder | Derived artifacts only; scripts regenerate them from Markdown; agents never edit them directly |
| `brain/state/*.json` and `*.jsonl` | Runtime, journal, cache, and model-call modules | Private operational state; never promoted to player-visible canon without a reviewed projection |

No module may silently rewrite another workflow's owned section. Cross-file changes must be one proposal with explicit dependencies and one transaction. If two workflows need the same section, the Orchestrator creates a combined proposal and identifies the owning workflow as the final validator.

## 15. Command contract

Commands are control-plane operations, not gameplay turns. They do not advance time unless the command explicitly completes a reviewed day/setup transition.

| Command | Valid use | Effect |
| --- | --- | --- |
| `/help` | Any gate | Display commands; no state change |
| `/status` | Any gate | Display current phase, play gate, pending operation, and saved stage |
| `/retry` | `retry` | Restart the failed stage from its saved pre-stage snapshot |
| `/review` | Draft/day-end pending | Prepare the current setup or day-end proposal for review |
| `/approve` | Normal review gates | Approve the exact reviewed proposal; never confirms campaign replacement |
| `/approve-reset` | Final setup/reset review only | Explicitly approve replacement of the current campaign |
| `/cancel-setup` | Setup draft/review | Discard setup draft/staged replacement; preserve active campaign |
| `/quit` | Any gate | Persist resumable state and exit |
| `/new-game` | Outside active resolution | Begin a draft replacement; preserve the active campaign until `/approve-reset` |
| `/new-character` | Open campaign | Begin a player-character draft without changing active canon |
| `/new-party-member` | Open campaign | Begin a party-member draft without changing active canon |
| `/add` | Setup draft | Add another character to the draft |
| `/main NAME` | Setup draft | Select the party's main player character |
| `/undo` | Setup draft | Undo the last setup input without touching campaign files |
| `/end-day` | Open campaign | Begin chronological day-end processing; it does not skip review |
| `/specialists` | Outside active resolution | Show stored specialist proposals; no unlock occurs |
| `/install NAME` | Specialist proposal review | Propose installation; explicit approval is still required |
| `/back-setup` | Sequential `setup_review` with a prior approved batch | Reopen the prior batch as a new revision without restarting the campaign |
| Player revision text | Any review gate | Rebuild the proposal; previous approval becomes invalid |
| `/next-file` | Multi-file review | Advance the current proposal file cursor without changing state |
| `/cancel-operation` | Unapplied review | Discard the pending proposal without changing campaign files |
| `/pause` and `/resume` | Open/paused gates | Pause or resume gameplay without discarding state |

The terminal adapter may expose aliases, but aliases must map to the same operation contract and journal events. Unknown commands are not silently interpreted as gameplay actions when a control-plane gate is active.

## 16. Proposed implementation seams (not yet implemented)

Keep a small terminal-facing interface for submitting input, answering pending questions, reviewing/approving proposals, and resuming. Internally compose deep modules around actual responsibilities:

- **Orchestrator:** owns flow selection, gates, ordering, phase synchronization, and resume.
- **State/journal module:** owns identities, state versions, snapshots, saved dice, and effect receipts.
- **Model-call module:** owns provider calls, exact request history, result validation metadata, and safe reuse. Existing DeepSeek and Ollama calls plus deterministic test adapters use this seam.
- **Visibility module:** supplies explicit private and player-visible projections for specialists, narration, review, and logs.
- **Approval/editor module:** owns immutable proposals, expected hashes, staging, rollback/recovery, and reconciliation receipts.
- **Existing brain/backend modules:** retain routing, evidence, advisory analysis, resolution, narration, working recording, and NPC/phase planning.

Physical private-storage layout and the concrete terminal commands are implementation details, not additional game rules. Prefer callable Python interfaces; adapt the spaced `outside game/` folder deliberately rather than scattering path manipulations across the runtime.

## 17. Acceptance checks

1. Setup can create several characters, choose a main character, revise dependent values, and preserve the old campaign on cancellation.
2. Confirmed replacement preserves lore/rules, resets only campaign state, deletes the old cache, and retains new setup history.
3. Cache Specialist runs first and supplies current scoped context in every flow; failed mandatory analysis blocks dependent work.
4. Foreground stages run in the agreed order; dice and clarification loops resume the same logical turn.
5. All model requests/results and repairs are captured without credentials; identical valid requests reuse results, changed inputs do not.
6. Replaying completed stages never repeats resource effects, recorded turns, ticks, rolls, or approved file changes.
7. Backend starts only on crossed phase boundaries, can overlap narration, and blocks the next action until required work completes.
8. Half-phase actions accumulate correctly; failed earlier phases prevent later phase commitment.
9. Schedules/orders override AI sleep decisions; naps do not end the day; interrupted sleep grants only earned rest.
10. Hidden data cannot reach TEMP_MEMORY, admin review, player output, or game-log export through nested prompts, notes, or cache hits.
11. Day-end blocks play until the final combined proposal is approved and atomically applied.
12. Player revisions cause dependent recalculation, state/cache invalidation, and renewed approval.
13. Immediate approved admin edits reconcile pending working records and indexes.
14. World event setup uses one saved d100, remains pending until encounter, and cannot miss its next-day deadline.
15. Editor rejects unapproved/stale content, composes same-file edits, and recovers from failure at every multi-file write/checkpoint step.
16. Restart preserves draft setup, pending questions, approvals, interrupted sleep, completed phase work, and unfinished next-day preparation.

Rule-derived edge cases (for example, consequences of END = 0, allowed numeric stat granularity, and incompatible character backgrounds) must be validated against the actual rules during implementation; do not silently add balancing restrictions or invent missing lore.
