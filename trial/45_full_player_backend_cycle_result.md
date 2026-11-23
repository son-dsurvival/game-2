# Full Player -> Backend -> Meeting Cycle

## Player Prompts

1. `Tell Renn to collect medicinal herbs in the north grove. I search the market for a map.`
2. `Travel along the north road.`
3. `Enter the north grove and meet Renn.`

## 1. Did the game correctly turn to the backend?

**True** — three player turns created three private backend phase ticks.

## 2. Backend resolution

The backend Lead Resolver test adapter resolved Renn's autonomous action on every tick.
The test assumption was **2 medicinal herbs per phase**:

```text
2 herbs x 3 phases = 6 herbs
```

- Backend resolutions: **3**
- Final herb total: **6**
- Resources calculated: **True**

## 3. Result after the player meets Renn

> The player continues toward the north grove.
Renn is here, still collecting medicinal herbs. The backend records 6 herbs gathered.

- Player met Renn after turn three: **True**
- Calculated result was revealed: **True**

## Status

**PASSED**

Structured detail: `trial/45_full_player_backend_cycle_result.json`
