"""Non-destructive party drafting, independent of providers and document writes."""
from __future__ import annotations

import math
import uuid
from typing import Any

from brain.runtime_state import RuntimeStateStore

STATS = ('AGI', 'INT', 'STR', 'END', 'WIS', 'PRE')


class SetupDrafts:
    def __init__(self, state: RuntimeStateStore):
        self.state = state

    def begin(self, mode: str = 'new_game') -> None:
        if mode not in {'new_game', 'new_character', 'new_party_member'}:
            raise ValueError('Unknown character mode.')
        current = self.state.load()
        if current.get('operation') or current.get('draft'):
            raise RuntimeError('Finish the pending operation or cancel the existing draft first.')
        if mode != 'new_game' and current['play_gate'] != 'open':
            raise RuntimeError('Adding characters requires an active campaign.')
        campaign_id = current.get('campaign_id') if mode != 'new_game' else None
        self.state.save({'draft': {'campaign_id': campaign_id or 'campaign-' + uuid.uuid4().hex,
                                   'characters': [], 'main_character': None, 'mode': mode,
                                   'previous_gate': current['play_gate'], 'question': 'identity', 'partial': {}},
                         'play_gate': 'setup_draft', 'message': 'Identity: enter name | age | race.'})

    def add(self, identity: dict[str, Any], stats: dict[str, Any], description: str, character_class: str) -> None:
        state = self.state.load()
        if state['play_gate'] not in {'setup_draft', 'setup_review'}:
            raise RuntimeError('Start character setup first.')
        if not all(str(identity.get(key, '')).strip() for key in ('name', 'age', 'race')):
            raise ValueError('Identity requires name, age and race.')
        values = {str(key).upper(): value for key, value in stats.items()}
        if set(values) != set(STATS) or any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in values.values()):
            raise ValueError('Provide six non-negative finite stats: AGI, INT, STR, END, WIS, PRE.')
        if not math.isclose(sum(values.values()), 30, abs_tol=1e-9):
            raise ValueError('Starting stats must total 30.')
        if not description.strip() or not character_class.strip():
            raise ValueError('Provide a description and class concept/mechanics, or request an AI class.')
        draft = state['draft']
        characters = [item for item in draft['characters'] if item['identity']['name'].casefold() != str(identity['name']).casefold()]
        characters.append({'identity': identity, 'stats': values, 'description': description, 'class': character_class})
        draft.update(characters=characters, question='party', partial={})
        self.state.save({'draft': draft, 'proposal': None, 'operation': None, 'play_gate': 'setup_draft',
                         'message': 'Character drafted. /add for another, /main NAME, or /review.'})

    def choose(self, name: str) -> None:
        state = self.state.load()
        if state['play_gate'] != 'setup_draft' or not state.get('draft'):
            raise RuntimeError('Start character setup first.')
        draft = state['draft']
        names = [item['identity']['name'] for item in draft['characters']]
        if name not in names:
            raise ValueError('Choose a character from the drafted party.')
        if draft.get('mode') in {'new_character', 'new_party_member'}:
            if len(draft['characters']) != 1:
                raise ValueError('Add exactly one character at a time mid-campaign.')
            # Mid-campaign additions never replace the campaign's main character.
            draft['character'] = name
        else:
            draft['main_character'] = name
        self.state.save({'draft': draft})

    def answer(self, text: str) -> None:
        state = self.state.load()
        draft = state.get('draft')
        if not draft or state['play_gate'] != 'setup_draft':
            raise RuntimeError('No character question is pending.')
        partial = draft['partial']
        question = draft['question']
        if question == 'identity':
            parts = [part.strip() for part in text.split('|')]
            if len(parts) != 3 or not all(parts):
                raise ValueError('Use name | age | race.')
            partial['identity'] = dict(zip(('name', 'age', 'race'), parts))
            draft['question'] = 'stats'
            message = 'Distribute 30 points: AGI INT STR END WIS PRE (six numbers). Stats below 3 incur rule penalties.'
        elif question == 'stats':
            numbers = [float(value) for value in text.split()]
            if len(numbers) != 6 or any(not math.isfinite(value) or value < 0 for value in numbers) or not math.isclose(sum(numbers), 30):
                raise ValueError('Enter six non-negative numbers totaling 30.')
            partial['stats'] = dict(zip(STATS, numbers))
            draft['question'] = 'description'
            message = 'Describe the character, background and personality.'
        elif question == 'description':
            if not text.strip():
                raise ValueError('A description is required.')
            partial['description'] = text
            draft['question'] = 'class'
            message = 'Describe the class concept/mechanics, or ask the AI to create one.'
        elif question == 'class':
            self.add(partial['identity'], partial['stats'], partial['description'], text)
            return
        else:
            raise ValueError('Use /add, /main NAME, /review, or /cancel-setup.')
        self.state.save({'draft': draft, 'message': message})

    def another(self) -> None:
        state = self.state.load()
        if state['play_gate'] != 'setup_draft':
            raise RuntimeError('No editable party draft.')
        draft = state['draft']
        if draft.get('mode') in {'new_character', 'new_party_member'} and draft['characters']:
            raise ValueError('Mid-campaign additions take one character at a time; review or cancel.')
        draft.update(question='identity', partial={})
        self.state.save({'draft': draft, 'message': 'Identity: name | age | race.'})

    def cancel(self) -> None:
        state = self.state.load()
        if state['play_gate'] not in {'setup_draft', 'setup_review', 'retry'} or not state.get('draft'):
            raise RuntimeError('No cancellable setup draft.')
        operation = state.get('operation') or {}
        if operation.get('approved') or operation.get('receipt'):
            raise RuntimeError('Replacement was already approved; resume it rather than cancelling.')
        self.state.save({'play_gate': state['draft']['previous_gate'], 'draft': None, 'operation': None, 'proposal': None, 'message': 'Setup cancelled; existing campaign preserved.'})
