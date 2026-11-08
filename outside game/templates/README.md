# Administrative document templates

Templates define readable Markdown structure. They do not contain campaign facts.

Known targets:

- `status sheet.md` → `character_status.md`
- `character relationship.md` → `character_relationship.md`
- `Ledger Resources.md` → `ledger_resources.md`
- `Experimentation Register.md` → `experimentation_register.md`
- `🌍 CORE WORLD FRAME (REFINED).md` → `core_world_frame.md`
- `Branch Registry.md` → `branch_registry.md`

Entry templates for approved Admin Editor updates:

- `core_world_event.md` → one event entry under `## Event log`
- `core_world_game_log.md` → one player-facing turn under `## Game log`
- `experiment_entry.md` → experiment entries under `Experimentation Register.md`
- `TEMP_MEMORY.md` → `temp_memory.md` (Recorder-owned; not edited directly by the Admin Editor)

Repeatable block templates are used for stat modifiers, class modifiers, effect modifiers, active skills, equipment, modifier groups (group → character → multiple modifiers), party relationships, non-party relationships, resources, facilities, experiments, background directives, world-log entries, temporary-memory records, and branch entries. Modifier-group entries include scenario use, activation conditions, limitations, stacking, evidence, and Admin Agent defense. Relationship scores, relationship dynamics, and character behavior are nested blocks.

The editor fills labels and repeatable blocks from an approved proposal. It must preserve formulas, headings, and existing facts. It must not write JSON blobs into campaign Markdown. A new branch template is created only after the branch proposal is approved.
