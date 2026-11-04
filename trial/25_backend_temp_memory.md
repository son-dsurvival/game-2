# Dummy Experimentation Register

## Active Background Directives

Only explicitly safe teammate/background status is mirrored here. Complete directive metadata remains private runtime state.

### directive-seris-hunt-001
actor: Seris
task: Hunt monsters near the eastern road
location: Eastern road
status: active
last processed tick: day-4-evening
ooc visibility: teammate_status
roleplay visibility: hidden

### directive-ava-rest-001
actor: Ava
task: Stand watch at the camp
location: Camp
status: active
last processed tick: day-4-evening
ooc visibility: teammate_status
roleplay visibility: hidden

## Outside Player Perspective Turns

This register mirrors only explicitly safe teammate/background status. True surprises, enemy plans, unrevealed world events, and private tick detail remain in private runtime storage until normal play reveals them.

### day-4-evening
day: 4
phase: Evening
status: committed

#### Off-Screen Actions
- actor: Seris
  assigned task: Hunt monsters near the eastern road
  chosen action: Scout the road before engaging the nearest monster
  result: successful
  ooc visibility: teammate_status
  roleplay visibility: hidden
- actor: Ava
  assigned task: Stand watch at the camp
  chosen action: Remain idle: actor is resting
  result: idle
  ooc visibility: teammate_status
  roleplay visibility: hidden

#### Automatic Updates
- state: current MP; before: 95; delta: 5; after: 100; ooc visibility: teammate_status; roleplay visibility: visible

#### Resource Changes
- resource: arrows; before: 20; delta: -3; after: 17; ooc visibility: teammate_status; roleplay visibility: hidden

#### World Updates
- None.

#### Player Report

status: not yet reported
