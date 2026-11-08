# Specialist lanes

Every normal turn runs the five core specialists against the same frozen Evidence Bundle. The cache lane runs first; the remaining four lanes then run concurrently with its compact context:

- **cache** — reviews the new conversation against the prior cache and extracts durable facts, active threads, commitments, pending event conditions, unresolved questions, and expiring facts. It is advisory memory only.
- **rules** — combat and noncombat rules, difficulty, XP, time, resources, experiments, validity, and costs.
- **character** — player and named-character status, relationships, modifiers, autonomy, motives, and participation.
- **special** — unlocked, world-specific branches such as business, alchemy, class, politics, relay systems, and factions.
- **create** — audits the rules, state, characters, lore, and active branches; proposes a bounded specialist when a recurring branch is not covered and checks that existing scopes remain current.

The cache specialist never resolves outcomes, changes canon, or writes files. Its `cache_delta` is passed to the other specialists and the Lead Resolver. Durable persistence remains the Recorder's responsibility.

`brain/branch_discovery.py` scans lore, rules, Event/Game logs, TEMP_MEMORY, runtime state, conversation history, cache, and specialist findings for recurring uncovered domains. It reports explainable `lore_candidate` and active `candidate` branches to the Create Specialist and Lead Resolver, and persists those candidates to the Branch Registry by default. Discovery never unlocks a branch by itself; resolved confirmation and approval remain required.

Domain specialists such as `business`, `class`, `relay`, `difficulty`, and `modifier` remain available for explicit branch routing and replay compatibility. `modifier_creation` is a separate triggered specialist: it audits history for new reusable Effect Modifiers and is also run during new-game setup as a no-grant review.

Create proposals are validated and returned as `created_specialists` with status `proposed`. They are not written to campaign files or executed automatically.
