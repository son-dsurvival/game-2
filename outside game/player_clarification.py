"""Convert internal clarification records into safe player-facing questions."""
from __future__ import annotations

from typing import Any


_INTERNAL_MARKERS = (
    'template', 'exact current', 'status sheet', 'ledger',
    'experimentation register', 'core world frame', 'event log section',
    'file contents', 'markdown', 'backend', 'evidence bundle',
    'normal xp', 'class xp', 'registered', 'admin agent', 'specialist',
    'derivation formula', 'rule formula',
)


class PlayerClarification:
    """Translate a complete internal response into safe player-facing data."""

    @classmethod
    def present(cls, response: dict[str, Any], *, fallback: str | None = None) -> dict[str, str] | None:
        """Inspect the full Admin Agent result without exposing backend fields."""
        question = cls.from_response(response, fallback=fallback)
        if not question:
            return None
        return {'question': question, 'source': 'player_clarification'}

    @classmethod
    def from_response(cls, response: dict[str, Any], *, fallback: str | None = None) -> str | None:
        candidates: list[Any] = []
        for key in ('player_question', 'question'):
            candidates.append(response.get(key))
        diagnosis = response.get('diagnosis')
        if isinstance(diagnosis, dict):
            candidates.append(diagnosis.get('player_question'))
        questions = response.get('questions')
        if isinstance(questions, list):
            candidates.extend(questions)
        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            text = candidate.strip()
            if text and not cls._internal(text):
                return text
        return fallback

    @classmethod
    def from_setup_draft(cls, draft: dict[str, Any]) -> str | None:
        characters = draft.get('characters') or []
        if not characters:
            return 'Tell me about the first character for this new game.'
        if not draft.get('main_character'):
            names = ', '.join(
                str(item.get('identity', {}).get('name'))
                for item in characters if isinstance(item, dict)
            )
            return f'Choose the main character with /main NAME. Available characters: {names}'
        if not draft.get('party_done'):
            return 'Are you finished adding characters? If so, use /main NAME to complete the party.'
        return None

    @classmethod
    def _internal(cls, text: str) -> bool:
        lowered = text.casefold()
        return any(marker in lowered for marker in _INTERNAL_MARKERS)
