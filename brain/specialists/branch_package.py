"""Validated, template-backed packages for newly discovered branches."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


DEFAULT_SECTIONS = (
    'Current State',
    'Rules and Constraints',
    'Resources and Costs',
    'Evidence and Progress',
    'Consequences and Open Questions',
)
_NAME = re.compile(r'^[a-z][a-z0-9_]{1,31}$')


@dataclass(frozen=True)
class BranchPackage:
    name: str
    purpose: str
    questions: tuple[str, ...]
    activation_tags: tuple[str, ...]
    template: str
    sections: tuple[str, ...]
    evidence_requirements: tuple[str, ...]

    @classmethod
    def from_definition(cls, value: dict[str, Any]) -> 'BranchPackage':
        name = str(value.get('name', '')).strip().casefold()
        if not _NAME.fullmatch(name):
            raise ValueError('Branch package name must be lowercase snake_case.')
        purpose = str(value.get('purpose', '')).strip()
        if not purpose:
            raise ValueError('Branch package requires a purpose.')
        questions = _strings(value.get('questions'), limit=8)
        if not questions:
            raise ValueError('Branch package requires specialist questions.')
        tags = _strings(value.get('activation_tags'), limit=12)
        if any(not re.fullmatch(r'[a-z][a-z0-9_.-]*', tag) for tag in tags):
            raise ValueError('Branch activation tags must be safe identifiers.')
        template = str(value.get('template') or f'branch_{name}.md').strip()
        if not re.fullmatch(r'[a-z][a-z0-9_-]*\.md', template):
            raise ValueError('Branch template must be a safe Markdown filename.')
        sections = _strings(value.get('sections'), limit=12) or DEFAULT_SECTIONS
        evidence = _strings(value.get('evidence_requirements'), limit=12) or (
            'A resolved turn must provide evidence that this branch is established.',
        )
        return cls(name, purpose, questions, tags, template, sections, evidence)

    def render_template(self) -> str:
        lines = [f'# {self.name.replace("_", " ").title()}', '', f'Purpose: {self.purpose}', '']
        for section in self.sections:
            lines.extend([f'## {section}', 'status:', 'evidence:', 'notes:', ''])
        lines.extend(['## Branch Rules and Evidence', ''])
        lines.extend(f'- {item}' for item in self.evidence_requirements)
        return '\n'.join(lines).rstrip() + '\n'


def _strings(value: Any, *, limit: int) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return ()
    result = []
    for item in value[:limit]:
        text = str(item).strip()
        if text:
            result.append(text.replace('\n', ' '))
    return tuple(dict.fromkeys(result))
