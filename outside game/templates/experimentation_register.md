# Experimentation Register

## Active Experiments

### {experiment name}
character:
branch:
method:
materials:
location:
started:
current phase:
status:

#### Intended Result

#### Current Evidence

#### Costs and Risks

- resource:
- before:
- delta:
- after:

#### Practice Carryover

value:
source:

## Completed Experiments

### {experiment name}
character:
branch:
method:
status:
started:
completed:
result:

#### Evidence

#### Derived Refinement

#### New Modifier

name:
description:
effect:
where it applies:

## Outside Player Perspective Turns

This section mirrors only explicitly safe teammate/background status that occurred outside the player's direct perspective. It is readable by the player out of character. True surprises, enemy plans, unrevealed world events, and private tick detail remain in `brain/state/` until normal play reveals them. Entries marked `roleplay visibility: hidden`, `offscreen`, or similar are not character knowledge: do not quote them in roleplay, narrate the player character as knowing them, or use them to choose an in-character action until they are revealed through play.

### {tick id}
day:
phase:
previous phase:
status:
ooc visibility:
roleplay visibility:

#### Off-Screen Actions

- actor:
  assigned task:
  chosen action:
  result:
  ooc visibility:
  roleplay visibility:

#### Automatic Updates

- state:
  before:
  delta:
  after:
  ooc visibility:
  roleplay visibility:

#### Resource Changes

- resource:
  before:
  delta:
  after:
  reason:
  ooc visibility:
  roleplay visibility:

#### World Updates

- description:
  ooc visibility:
  roleplay visibility:

#### Player Report

status: not yet reported

## Active Background Directives

### {directive id}
actor:
task:
location:
constraints:
started:
expires:
status:
last processed tick:
assigned by:
ooc visibility:
roleplay visibility:

## Experiment Rules and Notes

- Experiments and off-screen turns are stored as readable Markdown.
- Do not write JSON blobs into this document.
- The player may read this register out of character, but it contains only entries explicitly labelled with an OOC-safe visibility such as `teammate_status` or `background_status`.
- A roleplay-hidden/off-screen label limits character knowledge and Narrator disclosure; it does not hide an otherwise mirrored record.
- Unlabelled entries default to private runtime storage and are never mirrored here.
