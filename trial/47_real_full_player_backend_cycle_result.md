# Full Player -> Backend -> Meeting Cycle

## Player Prompts

1. `Tell Renn to collect medicinal herbs in the north grove. I search the market for a map.`
2. `Travel along the north road.`
3. `Enter the north grove and meet Renn.`

## 1. Did the game correctly turn to the backend?

**True** — three player turns created three committed private backend phase ticks; transient retry attempts were not committed twice.

## 2. Backend resolution

The real Backend Lead Resolver resolved Renn's autonomous action on every tick.
No herbs-per-phase value was supplied by this test. The quantity below came from
`resource_changes` returned by the Lead Resolver.

- Backend resolver attempts: **4**
- Committed backend resolutions: **3**
- Final herb total: **3**
- Resources calculated by Lead Resolver: **True**
- Resolver-decided total: **3 medicinal herbs**

## 3. Result after the player meets Renn

> The player continues toward the north grove.
Renn is here, still collecting medicinal herbs. The backend records 3 herbs gathered.

- Player met Renn after turn three: **True**
- Calculated result was revealed: **True**

## Status

**PASSED**

Structured detail: `trial/47_real_full_player_backend_cycle_result.json`
