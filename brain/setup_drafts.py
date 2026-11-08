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
        if mode == 'new_game' and (current.get('draft') or current.get('proposal')):
            # Starting a new game explicitly replaces an unfinished setup draft
            # or review. No campaign files have changed until approval.
            self.state.save({
                'draft': None,
                'proposal': None,
                'operation': None,
                'pending_clarification': None,
            })
            current = self.state.load()
        if current.get('operation') or current.get('draft'):
            raise RuntimeError('Finish the pending operation or cancel the existing draft first.')
        if mode != 'new_game' and current['play_gate'] != 'open':
            raise RuntimeError('Adding characters requires an active campaign.')
        campaign_id = current.get('campaign_id') if mode != 'new_game' else None
        main_character = current.get('main_character') if mode != 'new_game' else None
        prompt = ('Tell me about your character in your own words. Include anything you already know: name, age, ancestry, '
                  'background, personality, abilities, or class idea.')
        if main_character:
            prompt += f' The campaign main character is already {main_character}; it will not change.'
        draft = {'campaign_id': campaign_id or 'campaign-' + uuid.uuid4().hex,
                 'characters': [], 'main_character': main_character, 'mode': mode,
                 'previous_gate': current['play_gate'], 'previous_message': current.get('last_in_game_narration') or current.get('message', ''),
                 'previous_position': current.get('position'), 'question': 'identity',
                 'partial': {}, 'conversation': [], 'party_done': False}
        self.state.save({'draft': draft, 'play_gate': 'setup_draft', 'message': prompt})
        self.state.append_event(
            'character_setup_started',
            operation_type='out_of_game',
            mode=mode,
            campaign_id=draft['campaign_id'],
            position_before=current.get('position'),
            previous_narration=draft['previous_message'],
            status='in_progress',
        )

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
        draft.update(characters=characters, question='party', partial={}, conversation=[], party_done=False)
        message = 'Character drafted. Tell me about another character, or choose the main character when the party is ready.'
        if draft.get('main_character'):
            message = f'Character drafted. {draft["main_character"]} remains the campaign main character.'
        self.state.save({'draft': draft, 'proposal': None, 'operation': None, 'play_gate': 'setup_draft',
                         'message': message})

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
            # Choosing the main character explicitly closes the new-game
            # party-drafting question. The player can still use /add first
            # if they want to add more characters.
            draft['party_done'] = True
        # Any conversational partial belongs to an unfinished character turn;
        # choosing the main character explicitly completes that ambiguity.
        draft['partial'] = {}
        draft['question'] = 'party'
        self.state.save({'draft': draft})

    def record_chat_input(self, text: str) -> None:
        """Persist the player's setup message before any model call."""
        state = self.state.load()
        draft = state.get('draft')
        if not draft or state['play_gate'] != 'setup_draft':
            raise RuntimeError('No character question is pending.')
        conversation_value = draft.get('conversation')
        conversation: list[dict[str, str]] = conversation_value if isinstance(conversation_value, list) else []
        conversation.append({'role': 'user', 'content': text})
        draft['conversation'] = conversation
        self.state.save({'draft': draft})

    def save_chat_message(self, message: str) -> None:
        state = self.state.load()
        draft = state.get('draft')
        if not draft or state['play_gate'] != 'setup_draft':
            raise RuntimeError('No character question is pending.')
        draft['message'] = message
        self.state.save({'draft': draft, 'message': message})

    def apply_chat(self, response: dict[str, Any]) -> None:
        """Apply an AI-extracted setup turn, while keeping all validation local."""
        state = self.state.load()
        draft = state.get('draft')
        if not draft or state['play_gate'] != 'setup_draft':
            raise RuntimeError('No character question is pending.')
        patch_value = response.get('draft')
        patch: dict[str, Any] = patch_value if isinstance(patch_value, dict) else {}
        partial_value = draft.get('partial')
        partial: dict[str, Any] = partial_value if isinstance(partial_value, dict) else {}
        draft['partial'] = partial
        for field in ('identity', 'stats', 'description', 'class'):
            value = patch.get(field)
            if value not in (None, '', {}):
                if field in {'identity', 'stats'} and isinstance(value, dict):
                    existing_value = partial.get(field)
                    existing: dict[str, Any] = existing_value if isinstance(existing_value, dict) else {}
                    partial[field] = {**existing, **value}
                else:
                    partial[field] = value
        conversation_value = draft.get('conversation')
        conversation: list[dict[str, str]] = conversation_value if isinstance(conversation_value, list) else []
        draft['conversation'] = conversation
        user_message = str(response.get('user_message', '')).strip()
        if user_message and not (conversation and conversation[-1].get('role') == 'user' and conversation[-1].get('content') == user_message):
            conversation.append({'role': 'user', 'content': user_message})
        assistant_message = str(response.get('assistant_message', '')).strip()
        if assistant_message:
            conversation.append({'role': 'assistant', 'content': assistant_message})

        main_hint = response.get('main_character')
        if isinstance(main_hint, str) and main_hint.strip():
            names = [item.get('identity', {}).get('name', '') for item in draft.get('characters', []) if isinstance(item, dict)]
            matches = [name for name in names if name.casefold() == main_hint.casefold()]
            if not matches:
                matches = [name for name in names if name.casefold().startswith(main_hint.casefold())]
            if len(matches) == 1:
                draft['main_character'] = matches[0]
        if response.get('party_done'):
            draft['party_done'] = True

        if response.get('complete'):
            try:
                self.add(partial.get('identity', {}), partial.get('stats', {}),
                         str(partial.get('description', '')), str(partial.get('class', '')))
                return
            except (TypeError, ValueError) as exc:
                draft['message'] = f'{assistant_message}\nBefore I finalize that character: {exc}'.strip()
        else:
            draft['message'] = assistant_message or 'Tell me a little more about the character.'
        # The chatbot uses the persisted partial/conversation; identity is also
        # the deterministic fallback if the provider is temporarily unavailable.
        draft['question'] = 'identity'
        self.state.save({'draft': draft, 'message': draft.get('message', '')})

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
            raise ValueError('Tell me about the character, or use /add, /main NAME, /review, or /cancel-setup.')
        self.state.save({'draft': draft, 'message': message})

    def another(self) -> None:
        state = self.state.load()
        if state['play_gate'] != 'setup_draft':
            raise RuntimeError('No editable party draft.')
        draft = state['draft']
        if draft.get('mode') in {'new_character', 'new_party_member'} and draft['characters']:
            raise ValueError('Mid-campaign additions take one character at a time; review or cancel.')
        draft.update(question='identity', partial={}, conversation=[], party_done=False)
        self.state.save({'draft': draft, 'message': 'Tell me about the next character in your own words.'})

    def cancel(self) -> None:
        state = self.state.load()
        if state['play_gate'] not in {'setup_draft', 'setup_review', 'retry'} or not state.get('draft'):
            raise RuntimeError('No cancellable setup draft.')
        operation = state.get('operation') or {}
        if operation.get('approved') or operation.get('receipt'):
            raise RuntimeError('Replacement was already approved; resume it rather than cancelling.')
        previous_gate = state['draft']['previous_gate']
        self.state.save({'play_gate': previous_gate, 'draft': None, 'operation': None, 'proposal': None, 'message': 'Setup cancelled; existing campaign preserved.'})
        self.state.append_event(
            'setup_draft_cancelled',
            operation_type='out_of_game',
            campaign_id=state['draft'].get('campaign_id'),
            previous_gate=previous_gate,
            status='cancelled_by_player',
        )
