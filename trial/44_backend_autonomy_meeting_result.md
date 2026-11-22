# Backend Autonomy Meeting Test

## Scenario

- **Task A — Renn:** Collect medicinal herbs in the north grove.
- **Task A location:** north grove
- **Player Task B, Turn 1:** Search the market for a map.
- **Player Task B, Turn 2:** Travel along the north road.
- **Player Task B, Turn 3:** Enter the north grove and look for Renn.

## Backend Result

Renn continued Task A on all three backend ticks while the player independently performed Task B.
On the third turn, the player entered the north grove and met Renn still performing the assigned task.

### Resource Calculation

The test used an explicit temporary assumption of **2 medicinal herbs per phase**.
After 3 phases: **2 × 3 = 6 medicinal herbs returned**.

### Meeting Narration

> After searching the market and traveling north, the player enters the grove and finds Renn collecting medicinal herbs exactly as instructed.

## Verification

- Three player turns completed: **True**
- Three backend ticks committed: **True**
- Renn continued Task A: **True**
- Player Task B remained separate: **True**
- Meeting occurred after turn 3: **True**
- Directive completed at meeting tick: **True**
- Resource calculated each phase: **True**
- Total returned after three phases: **True** — 6 medicinal herbs
- Private background remained out of public register: **True**

## Status

**PASSED**

Structured detail: `trial/44_backend_autonomy_meeting_result.json`
