# Experimentation Register

## Active Experiments
{active experiments}

## Completed Experiments
{completed experiments}

## Outside Player Perspective Turns
{outside player ticks}

This section mirrors only explicitly safe teammate/background status that occurred outside the player's direct perspective. It is readable by the player out of character. True surprises, enemy plans, unrevealed world events, and private tick detail remain in `brain/state/` until normal play reveals them. Entries marked `roleplay visibility: hidden`, `offscreen`, or similar are not character knowledge: do not quote them in roleplay, narrate the player character as knowing them, or use them to choose an in-character action until they are revealed through play.

## Active Background Directives
{active background directives}

## Experiment Rules and Notes

- Experiments and off-screen turns are stored as readable Markdown.
- Do not write JSON blobs into this document.
- The player may read this register out of character, but it contains only entries explicitly labelled with an OOC-safe visibility such as `teammate_status` or `background_status`.
- A roleplay-hidden/off-screen label limits character knowledge and Narrator disclosure; it does not hide an otherwise mirrored record.
- Unlabelled entries default to private runtime storage and are never mirrored here.
