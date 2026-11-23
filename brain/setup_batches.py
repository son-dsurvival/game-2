"""Template-driven batches for new-campaign setup."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


TEMPLATE_NAMES = {
    'status sheet.md': 'character_status',
    'Ledger Resources.md': 'ledger_resources',
    'character relationship.md': 'character_relationship',
    'Experimentation Register.md': 'experimentation_register',
    'TEMP_MEMORY.md': 'temp_memory',
}


RESET_FILES = (
    'status sheet.md',
    'Ledger Resources.md',
    'character relationship.md',
    'Experimentation Register.md',
    'TEMP_MEMORY.md',
)
PRESERVED_FILES = ('Branch Registry.md', '🌍 CORE WORLD FRAME (REFINED).md')

# Starting Stat Modifier capacity follows the existing stat-value bands. This
# determines the number of modifier slots, not an automatic award.
STAT_MODIFIER_SLOT_BANDS = (
    (1000, 8), (500, 7), (200, 6), (100, 5), (50, 4),
    (20, 3), (10, 2), (5, 1),
)


def stat_modifier_slots(value: Any) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if number < 5:
        return 0
    for threshold, slots in STAT_MODIFIER_SLOT_BANDS:
        if number >= threshold:
            return slots
    return 0


def setup_changes_are_meaningful(batch_id: str, changes: object) -> bool:
    """Return whether a setup proposal adds meaningful player-facing state."""
    if not isinstance(changes, list):
        return False
    for change in changes:
        if not isinstance(change, dict):
            continue
        old = str(change.get('old_text', ''))
        new = str(change.get('new_text', ''))
        if old == new:
            continue
        if batch_id == 'status_active_skills':
            skill_blocks = re.findall(
                r'(?ms)^### Active Skills\s*\n(.*?)(?=^---\s*$|^#\s+|\Z)',
                new,
            )
            if skill_blocks and all(
                re.sub(r'\s+', ' ', block).strip().casefold()
                == 'no active system skills established.'
                for block in skill_blocks
            ):
                continue
            if old and old in new:
                addition = new.replace(old, '', 1)
                addition = re.sub(r'(?m)^### Active Skills\s*$', '', addition)
                addition = re.sub(r'(?m)^No active system skills established\.\s*$', '', addition)
                addition = re.sub(r'(?m)^---\s*$', '', addition)
                addition = re.sub(r'(?m)^# .*$\n?', '', addition)
                if not addition.strip():
                    continue
        return True
    return False


def starting_stat_modifier_slots(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Return deterministic starting slots for each drafted character/stat."""
    slots: list[dict[str, Any]] = []
    for character in draft.get('characters', []) if isinstance(draft, dict) else []:
        if not isinstance(character, dict):
            continue
        identity = character.get('identity') if isinstance(character.get('identity'), dict) else {}
        name = str(identity.get('name') or 'Unnamed Character')
        stats = character.get('stats') if isinstance(character.get('stats'), dict) else {}
        for raw_stat, value in stats.items():
            stat = str(raw_stat).upper()
            count = stat_modifier_slots(value)
            for slot in range(1, count + 1):
                slots.append({'character': name, 'stat': stat, 'slot': slot, 'stat_value': value})
    return slots


BATCHES: tuple[dict[str, Any], ...] = (
    {
        'id': 'status_identity_stats_derived', 'file': 'status sheet.md',
        'sections': ('Identity', 'Stats', 'Derived Stats'),
        'specialists': (),
        'purpose': 'Establish identity, approved base stats, deterministic derived values, and show both XP tracks as current XP / XP required for the next level. At Level 1, Tier 0, use Class XP 0 / 200 and Normal XP 0 / 500.',
    },
    {
        'id': 'status_stat_modifiers', 'file': 'status sheet.md',
        'sections': ('Stat Modifiers',),
        'specialists': ('create_stat_modifier',),
        'purpose': 'Generate three choices for every deterministic Stat Modifier slot allowed by each character’s stat values, including slots unlocked by character action. Strong evidence supports high-basis options; weak or absent evidence produces low or assumed-low generic options. More independent bases may justify a higher magnitude within the character’s tier.',
    },
    {
        'id': 'status_class_modifiers', 'file': 'status sheet.md',
        'sections': ('Class', 'Class Modifiers'),
        'specialists': ('class',),
        'purpose': 'Record class status and, for every available Class Modifier slot, provide five class-specific choices from which the player selects one. Do not grant a class or class modifier contrary to world rules.'
    },
    {
        'id': 'status_active_skills', 'file': 'status sheet.md',
        'sections': ('Active Skills',),
        'specialists': ('class',),
        'purpose': 'Record active system skills only when the rules and evidence support them.',
    },
    {
        'id': 'status_effect_modifiers', 'file': 'status sheet.md',
        'sections': ('Effect Modifiers',),
        'specialists': ('create_effect_modifier',),
        'purpose': 'Provide ten starting Effect Modifier choices per character; the player selects three. Generate the choices from the character description, with high-basis evidence supporting stronger effects within tier and low or absent basis producing low or assumed-low options.'
    },
    {
        'id': 'status_equipment', 'file': 'status sheet.md',
        'sections': ('Equipment',),
        'specialists': (),
        'purpose': 'Record background-supported equipment without inventing System items.',
    },
    {
        'id': 'ledger_resources', 'file': 'Ledger Resources.md',
        'sections': ('Current Resources', 'Materials', 'Facilities', 'Resource Rules and Notes'),
        'specialists': (),
        'purpose': 'Record starting resources and clearly label setup assumptions.',
    },
    {
        'id': 'relationships', 'file': 'character relationship.md',
        'sections': ('Player', 'Party Character Relationships', 'Non-Party Character Relationships'),
        'specialists': (),
        'purpose': 'Record party roles, autonomy, and relationship assumptions.',
    },
    {
        'id': 'experimentation', 'file': 'Experimentation Register.md',
        'sections': ('Active Experiments', 'Completed Experiments'),
        'specialists': ('create_effect_modifier',),
        'purpose': 'Start experiments and typed Effect Modifier design at an empty baseline.'
    },
    {
        'id': 'temporary_memory', 'file': 'TEMP_MEMORY.md',
        'sections': ('Current Session Position', 'Pending Session Canon'),
        'specialists': (),
        'purpose': 'Start temporary campaign memory without carrying forward old records.',
    },
)


def _template_sections(root: Path, filename: str) -> set[str]:
    template_name = TEMPLATE_NAMES[filename]
    path = root / 'outside game' / 'templates' / f'{template_name}.md'
    text = path.read_text(encoding='utf-8')
    sections: set[str] = set()
    for raw in re.findall(r'^#{2,4}\s+(.+?)\s*$', text, re.MULTILINE):
        label = re.sub(r'[{}]', '', raw).strip()
        aliases = {'identity': 'Identity', 'stats': 'Stats'}
        sections.add(aliases.get(label.casefold(), label))
    return sections


def batches(root: str | Path | None = None) -> list[dict[str, Any]]:
    """Return independent batches, validating their boundaries against templates."""
    path = Path(root).resolve() if root is not None else None
    result = []
    for batch in BATCHES:
        item = dict(batch, sections=list(batch['sections']), specialists=list(batch['specialists']))
        if path is not None:
            available = _template_sections(path, str(item['file']))
            missing = [section for section in item['sections'] if section not in available]
            if missing:
                raise RuntimeError(f"Template boundary missing for {item['id']}: {', '.join(missing)}")
            item['template_sections'] = sorted(available)
        result.append(item)
    return result
