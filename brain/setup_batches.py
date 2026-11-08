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


BATCHES: tuple[dict[str, Any], ...] = (
    {
        'id': 'status_identity_stats_derived', 'file': 'status sheet.md',
        'sections': ('Identity', 'Stats', 'Derived Stats'),
        'specialists': ('rules', 'character', 'class', 'world'),
        'purpose': 'Establish identity, approved base stats, deterministic derived values, and show both XP tracks as current XP / XP required for the next level. At Level 1, Tier 0, use Class XP 0 / 200 and Normal XP 0 / 500.',
    },
    {
        'id': 'status_stat_modifiers', 'file': 'status sheet.md',
        'sections': ('Stat Modifiers',),
        'specialists': ('rules', 'character', 'modifier_creation'),
        'purpose': 'Derive only background-supported stat modifiers from demonstrated capabilities.',
    },
    {
        'id': 'status_class_modifiers', 'file': 'status sheet.md',
        'sections': ('Class', 'Class Modifiers'),
        'specialists': ('rules', 'character', 'class'),
        'purpose': 'Record class status and class modifiers without granting a class contrary to world rules.',
    },
    {
        'id': 'status_active_skills', 'file': 'status sheet.md',
        'sections': ('Active Skills',),
        'specialists': ('rules', 'character', 'class'),
        'purpose': 'Record active system skills only when the rules and evidence support them.',
    },
    {
        'id': 'status_effect_modifiers', 'file': 'status sheet.md',
        'sections': ('Effect Modifiers',),
        'specialists': ('rules', 'character', 'modifier_creation'),
        'purpose': 'Review earned effect modifiers; a new campaign normally has none.',
    },
    {
        'id': 'status_equipment', 'file': 'status sheet.md',
        'sections': ('Equipment',),
        'specialists': ('rules', 'character'),
        'purpose': 'Record background-supported equipment without inventing System items.',
    },
    {
        'id': 'status_modifier_groups', 'file': 'status sheet.md',
        'sections': ('Modifier Groups',),
        'specialists': ('rules', 'character', 'modifier_creation'),
        'purpose': 'Review actual modifier-group placements; an empty section is valid and needs no placement.',
    },
    {
        'id': 'ledger_resources', 'file': 'Ledger Resources.md',
        'sections': ('Current Resources', 'Materials', 'Facilities', 'Resource Rules and Notes'),
        'specialists': ('rules', 'character'),
        'purpose': 'Record starting resources and clearly label setup assumptions.',
    },
    {
        'id': 'relationships', 'file': 'character relationship.md',
        'sections': ('Player', 'Party Character Relationships', 'Non-Party Character Relationships'),
        'specialists': ('rules', 'character'),
        'purpose': 'Record party roles, autonomy, and relationship assumptions.',
    },
    {
        'id': 'experimentation', 'file': 'Experimentation Register.md',
        'sections': ('Active Experiments', 'Completed Experiments'),
        'specialists': ('rules', 'modifier_creation'),
        'purpose': 'Start experiments and earned effect modifiers at an empty baseline.',
    },
    {
        'id': 'temporary_memory', 'file': 'TEMP_MEMORY.md',
        'sections': ('Current Session Position', 'Pending Session Canon'),
        'specialists': ('rules', 'character'),
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
