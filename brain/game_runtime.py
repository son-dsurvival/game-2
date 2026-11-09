"""Resumable orchestration. Terminal IO and model implementations live elsewhere."""
from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
from typing import Any

from backend.phase_clock import PHASES, PhaseClock
from brain.model_gateway import model_scope
from brain.dice import DiceJournal
from brain.persistence import atomic_json, atomic_text, runtime_lease
from brain.player_clarification import PlayerClarification
from brain.runtime_state import RuntimeStateStore


NEW_GAME_EMPTY_FILES = {
    'status sheet.md': '# Character Status\n\nNo characters have been established for this new game yet.\n',
    'Ledger Resources.md': '# Ledger Resources\n\nNo campaign resources have been established for this new game yet.\n',
    'character relationship.md': '# Character Relationships\n\nNo character or party relationships have been established for this new game yet.\n',
    'Experimentation Register.md': '# Experimentation Register\n\n## Active Experiments\n\nNone.\n\n## Completed Experiments\n\nNone.\n\nNo effect modifiers have been earned in this new game.\n',
    'TEMP_MEMORY.md': '# Temporary Campaign Memory\n\nNo temporary campaign records exist for this new game yet.\n',
}


JOURNAL_STAGE_NAMES = {
    'route': 'route',
    'evidence': 'evidence_prepared',
    'specialists': 'specialists_run',
    'admin': 'admin_analysis',
    'resolve': 'lead_resolver_decision',
    'narrate': 'narration_generated',
    'record': 'recorder',
    'background': 'background_processing',
    'finish': 'turn_completed',
    'prepare_setup': 'setup_batches',
    'prepare_character': 'character_proposal',
    'prepare_specialist': 'specialist_analysis',
    'prepare_day': 'day_end_preparation',
    'apply': 'proposal_application',
    'reconcile': 'reconciliation',
    'world': 'world_event_processing',
}


PROPOSAL_FILE_SUMMARIES = {
    'status sheet.md': 'Set up each character’s identity, Tier 0 status, derived values, background-based stat modifiers, skills, and equipment.',
    'Ledger Resources.md': 'Record starting money, resources, equipment assumptions, and shared household assets.',
    'character relationship.md': 'Record the main character, party membership, and starting relationship assumptions.',
    'Experimentation Register.md': 'Start the experimentation record with no earned effect modifiers or experiments.',
    'Branch Registry.md': 'Reset branch records for the new campaign without unlocking unearned branches.',
    'TEMP_MEMORY.md': 'Start temporary campaign memory with no carried-over pending records.',
    '🌍 CORE WORLD FRAME (REFINED).md': 'Preserve established lore and prepare the new campaign event and game logs.',
}

_PREVIEW_REDACTIONS = (
    'template', 'evidence', 'citation', 'backend', 'admin agent',
    'reason', 'old_text', 'new_text', 'source path', 'line range',
)
_PREVIEW_NUMERIC_ASSIGNMENT = re.compile(
    r'^([^=]{1,100})=\s*.*=\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*$'
)


def _player_safe_change_preview(change: dict[str, Any], *, limit: int = 80) -> list[str]:
    """Return proposed player-facing content without private implementation data."""
    text = change.get('new_text')
    if not isinstance(text, str) or not text.strip():
        return ['A file change is proposed, but no readable preview is available.']
    preview: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if preview and preview[-1] != '':
                preview.append('')
            continue
        lowered = line.casefold()
        if any(term in lowered for term in _PREVIEW_REDACTIONS):
            continue
        if '=' in line:
            numeric = _PREVIEW_NUMERIC_ASSIGNMENT.match(line)
            if numeric:
                line = f'{numeric.group(1).strip()}: {numeric.group(2)}'
            else:
                # Do not expose formulas or implementation assignments.
                continue
        preview.append(line)
        if len(preview) >= limit:
            break
    while preview and preview[-1] == '':
        preview.pop()
    if len(text.splitlines()) > limit:
        preview.append('…additional proposed content omitted from this preview.')
    return preview or ['The proposed file contains no additional player-facing text.']


class CampaignPipeline:
    def __init__(self, root: str | Path = '.', *, modules: Any = None):
        self.root = Path(root).resolve()
        self.state = RuntimeStateStore(self.root)
        if modules is None:
            from brain.game_modules import GameModules
            modules = GameModules(self.root)
        self.modules = modules
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='campaign-background')
        self._background: dict[str, Future[dict[str, Any]]] = {}

    def resume(self) -> dict[str, Any]:
        with runtime_lease(self.root):
            if hasattr(self.modules, 'recover'):
                self.modules.recover()
            state = self.state.load()
            draft = state.get('draft') or {}
            operation = state.get('operation') or {}
            # Recover a setup draft that was incorrectly advanced before the
            # party-completion gate was enforced. Never discard a proposal.
            if (state.get('play_gate') == 'awaiting_clarification'
                    and operation.get('kind') == 'setup'
                    and not state.get('proposal')
                    and draft.get('mode') == 'new_game'
                    and draft.get('party_done') is True
                    and draft.get('main_character')
                    and draft.get('characters')):
                self.state.save({
                    'operation': None,
                    'pending_clarification': None,
                    'play_gate': 'setup_draft',
                    'message': 'Character setup is complete. Choose the main character to prepare the proposal.',
                })
            return self.view()

    def status_report(self) -> dict[str, Any]:
        with runtime_lease(self.root):
            state = self.state.load()
            result = self.view()
            operation_value = state.get('operation')
            operation: dict[str, Any] = operation_value if isinstance(operation_value, dict) else {}
            raw_operation_id = operation.get('id')
            operation_id: str | None = str(raw_operation_id) if raw_operation_id else None
            all_events = self.state.journal_events()
            if not operation_id:
                completed: dict[str, Any] = next((item for item in reversed(all_events) if item.get('operation_id')), {})
                raw_completed_id = completed.get('operation_id')
                operation_id = str(raw_completed_id) if raw_completed_id else None
            events = self.state.journal_events(operation_id=operation_id) if operation_id else []
            stage_event: dict[str, Any] = next((item for item in reversed(events) if item.get('event') in {'stage_started', 'stage_retry_started', 'stage_waiting', 'stage_failed'}), {})
            latest: dict[str, Any] = events[-1] if events else {}
            latest_operation: dict[str, Any] = next((item for item in reversed(events) if item.get('operation_type')), {})
            original_event: dict[str, Any] = next((item for item in events if item.get('original_input')), {})
            gate_value = state.get('play_gate')
            gate = str(gate_value) if gate_value else None
            request_status = {
                'running': 'in_progress', 'background_pending': 'in_progress',
                'awaiting_clarification': 'awaiting_clarification',
                'retry': 'failed',
                'setup_review': 'awaiting_approval', 'character_review': 'awaiting_approval',
                'admin_review': 'awaiting_approval', 'day_end_review': 'awaiting_approval',
            }.get(gate or '', 'completed' if not operation else 'in_progress')
            result.update({
                'status': 'status',
                'request_status': request_status,
                'operation_type': operation.get('operation_type') or latest_operation.get('operation_type') or ('out_of_game' if operation.get('is_admin') else 'gameplay'),
                'operation_id': operation_id,
                'current_stage': stage_event.get('stage') or (self._journal_stage(operation.get('stage')) if operation else latest.get('stage')),
                'previous_stage': stage_event.get('previous_stage'),
                'next_stage': stage_event.get('next_stage'),
                'original_input': operation.get('original_input') or operation.get('message') or original_event.get('original_input') or latest.get('exact_input'),
            })
            return result

    def view(self) -> dict[str, Any]:
        state = self.state.load()
        operation = state.get('operation') or {}
        result = {
            'status': state['play_gate'], 'play_gate': state['play_gate'],
            'position': state['position'], 'message': state.get('message', ''),
            'turn_id': operation.get('id'), 'stage': operation.get('stage'),
        }
        if state.get('failure_reason'):
            result['failure_reason'] = state['failure_reason']
        if state.get('draft'):
            result['draft'] = {
                key: value for key, value in state['draft'].items()
                if key not in {'previous_gate', 'previous_message', 'previous_position', 'edit_history'}
            }
        if state.get('pending_clarification'):
            result['question'] = state['pending_clarification']
        proposal = state.get('proposal')
        if isinstance(proposal, dict):
            if isinstance(proposal.get('diagnosis'), dict):
                result['diagnosis'] = proposal['diagnosis']
            changes = [
                change for change in proposal.get('changes', [])
                if isinstance(change, dict)
                and str(change.get('target_file', '')).startswith('markdown_files/')
            ]
            index = state.get('proposal_file_index', 0)
            index = index if isinstance(index, int) and index >= 0 else 0
            result['proposal_files_total'] = len(changes)
            result['proposal_files_reviewed'] = min(index, len(changes))
            if index < len(changes):
                change = changes[index]
                target = str(change.get('target_file'))
                filename = Path(target).name
                result['proposal_file'] = {
                    'number': index + 1,
                    'total': len(changes),
                    'target_file': target,
                    'filename': filename,
                    'action': change.get('action', 'update'),
                    'summary': PROPOSAL_FILE_SUMMARIES.get(
                        filename,
                        'Apply the reviewed change to this campaign record.',
                    ),
                    'preview': _player_safe_change_preview(change),
                }
        if state.get('specialist_proposals'):
            result['specialist_proposals'] = list(state['specialist_proposals'].values())
        return result

    OUTSIDE_PLAY_GATES = {
        'setup_required', 'setup_draft', 'setup_review', 'character_review',
        'admin_review', 'day_end_pending', 'day_end_review',
        'new_game_pending', 'new_day_pending', 'paused',
    }

    def record_command(self, text: str) -> None:
        with runtime_lease(self.root):
            state = self.state.load()
            operation_value = state.get('operation')
            operation: dict[str, Any] = operation_value if isinstance(operation_value, dict) else {}
            self.state.append_event(
                'command_received',
                operation_id=operation.get('id'),
                command=text.split(' ', 1)[0] if text else '',
                exact_input=text,
                operation_type='out_of_game' if text.startswith('{') and text.endswith('}') else 'command',
                position_before=state.get('position'),
                play_gate_before=state.get('play_gate'),
            )

    def begin_player_interaction(self, text: str) -> str:
        with runtime_lease(self.root):
            state = self.state.load()
            operation_value = state.get('operation')
            operation: dict[str, Any] = operation_value if isinstance(operation_value, dict) else {}
            interaction_id = 'interaction-' + uuid.uuid4().hex
            self.state.append_event(
                'player_input_received',
                interaction_id=interaction_id,
                operation_id=operation.get('id'),
                exact_input=text,
                position_before=state.get('position'),
                play_gate_before=state.get('play_gate'),
                status='in_progress',
            )
            return interaction_id

    def complete_player_interaction(self, interaction_id: str, text: str, result: dict[str, Any], output: str) -> None:
        with runtime_lease(self.root):
            state = self.state.load()
            operation_value = state.get('operation')
            operation: dict[str, Any] = operation_value if isinstance(operation_value, dict) else {}
            self.state.append_event(
                'player_output_emitted',
                interaction_id=interaction_id,
                operation_id=result.get('turn_id') or operation.get('id'),
                output=output,
                result_status=result.get('status'),
                position_after=result.get('position') or state.get('position'),
                play_gate_after=state.get('play_gate'),
                status='completed',
            )
            self.state.append_player_exchange(
                result.get('position') if isinstance(result.get('position'), dict) else state.get('position'),
                text,
                output,
            )

    def fail_player_interaction(self, interaction_id: str, text: str, error: Exception) -> None:
        with runtime_lease(self.root):
            state = self.state.load()
            output = f'Error: {error}'
            self.state.append_event(
                'player_output_failed',
                interaction_id=interaction_id,
                error_type=type(error).__name__,
                error=str(error),
                position_after=state.get('position'),
                play_gate_after=state.get('play_gate'),
                status='failed',
            )
            self.state.append_player_exchange(state.get('position'), text, output)

    def submit(self, message: str) -> dict[str, Any]:
        if not message.strip():
            raise ValueError('Enter a message.')
        with runtime_lease(self.root):
            state = self.state.load()
            current_operation_value = state.get('operation')
            current_operation: dict[str, Any] = current_operation_value if isinstance(current_operation_value, dict) else {}
            self.state.append_event(
                'command_received',
                operation_id=current_operation.get('id'),
                operation_type='out_of_game' if (
                    message.strip().startswith('{') and message.strip().endswith('}')
                ) or state.get('play_gate') in self.OUTSIDE_PLAY_GATES else 'gameplay',
                exact_input=message,
                position_before=state.get('position'),
                play_gate_before=state.get('play_gate'),
            )
            normalized = message.strip().casefold()
            if normalized == '{pause}':
                return self._pause_locked(state)
            if normalized in {'{resume}', '/resume'}:
                return self._resume_play_locked(state)
            if state.get('operation') and state['play_gate'] in {'running', 'retry', 'background_pending'}:
                self._drive()
                state = self.state.load()
            if state['play_gate'] in {'day_end_review', 'setup_review', 'admin_review', 'character_review'}:
                if message.strip().startswith('{') and message.strip().endswith('}'):
                    return self._review_question(message, state)
                return self._revise(message, state)
            if state['play_gate'] == 'setup_draft':
                from brain.setup_drafts import SetupDrafts
                drafts = SetupDrafts(self.state)
                if hasattr(self.modules, 'setup_chat'):
                    # Never lose the player's message just because the model is
                    # slow, unavailable, or returns an unusable response.
                    drafts.record_chat_input(message)
                    response = self.modules.setup_chat(self.state.load().get('draft') or {}, message)
                    if response.get('status') != 'fallback':
                        drafts.apply_chat(response)
                        return self.view()
                    try:
                        drafts.answer(message)
                    except ValueError:
                        drafts.save_chat_message('I saved that message, but the setup assistant is temporarily unavailable. Try again, or use name | age | race for the deterministic fallback.')
                    return self.view()
                drafts.answer(message)
                return self.view()
            if state['play_gate'] == 'awaiting_clarification':
                operation = state['operation']
                if operation.get('kind') == 'setup':
                    draft = state.get('draft') or {}
                    if (draft.get('mode') == 'new_game' and draft.get('main_character')
                            and draft.get('characters')):
                        # Recover drafts created before main-character selection
                        # began marking the party complete.
                        draft['party_done'] = True
                        self.state.save({'draft': draft})
                        state = self.state.load()
                prior_clarification = state.get('pending_clarification')
                if isinstance(prior_clarification, dict):
                    operation['last_clarification'] = prior_clarification
                    link_id = prior_clarification.get('link_id')
                    links = operation.setdefault('clarification_links', [])
                    if isinstance(link_id, str):
                        for link in reversed(links):
                            if isinstance(link, dict) and link.get('id') == link_id:
                                link['answer'] = message
                                link['status'] = 'answered'
                                link['answered_revision'] = int(operation.get('revision', 0) or 0) + 1
                                operation['active_clarification_link_id'] = link_id
                                break
                operation['answers'].append(message)
                operation['revision'] += 1
                operation['stage_run_id'] = uuid.uuid4().hex
                self._journal_operation_event(
                    'clarification_answered', operation,
                    exact_response=message,
                    stage=self._journal_stage(operation.get('stage')),
                    status='in_progress',
                )
                if operation['kind'] in {'setup', 'character'}:
                    operation['stage'] = 'prepare_setup' if operation['kind'] == 'setup' else 'prepare_character'
                    operation['results'] = {}
                else:
                    operation['stage'] = 'evidence'
                    for key in ('evidence', 'specialists', 'resolution'):
                        operation['results'].pop(key, None)
                self.state.save({'operation': operation, 'pending_clarification': None, 'play_gate': 'running'})
            else:
                is_admin = message.strip().startswith('{') and message.strip().endswith('}')
                outside_gate = state['play_gate'] in self.OUTSIDE_PLAY_GATES
                if not is_admin and not outside_gate:
                    self.require_open_play()
                elif (is_admin and state['play_gate'] not in {'open', *self.OUTSIDE_PLAY_GATES}):
                    raise RuntimeError('Finish or resume the pending operation before administrative edits.')
                routed_message = message
                if outside_gate and not is_admin:
                    # Once outside roleplay, plain text is administrative text;
                    # the player is not required to add braces repeatedly.
                    routed_message = '{' + message + '}'
                operation = {
                    'id': 'turn-' + uuid.uuid4().hex, 'kind': 'turn', 'stage': 'route',
                    'operation_type': 'out_of_game' if is_admin or outside_gate else 'gameplay',
                    'is_admin': is_admin,
                    'attempt_id': uuid.uuid4().hex, 'stage_run_id': uuid.uuid4().hex,
                    'message': routed_message, 'original_input': message, 'answers': [], 'revision': 0, 'results': {},
                    'before': state['position'], 'dice': {}, 'return_gate': state['play_gate'],
                }
                self.state.save({'operation': operation, 'play_gate': 'running', 'message': ''})
                self._journal_operation_event(
                    'operation_started', operation,
                    original_input=message,
                    status='in_progress',
                    stage=self._journal_stage(operation['stage']),
                    position_before=state.get('position'),
                )
            return self._drive()

    def begin_setup(self) -> dict[str, Any]:
        with runtime_lease(self.root):
            previous = self.state.load()
            self._hard_reset_new_game()
            from brain.setup_drafts import SetupDrafts
            SetupDrafts(self.state).begin('new_game')
            state = self.state.load()
            draft = state.get('draft') or {}
            self.state.append_event(
                'new_campaign_started',
                campaign_id=draft.get('campaign_id'),
                previous_campaign_id=previous.get('campaign_id'),
                position=state.get('position'),
                status='in_progress',
            )
            return self.view()

    def _hard_reset_new_game(self) -> None:
        """Immediately start a new campaign without touching preserved world files."""
        previous_campaign_id = None
        try:
            previous_campaign_id = self.state.load().get('campaign_id')
        except RuntimeError:
            raise
        # A new campaign intentionally starts a fresh journal. The reset event
        # is the first record of the new campaign and contains only the old ID.
        self.state.journal_path.unlink(missing_ok=True)
        for filename, content in NEW_GAME_EMPTY_FILES.items():
            atomic_text(self.root / 'markdown_files' / filename, content)
        for filename in (
            'background_state.json', 'background_visible.md', 'pipeline_cache.json',
            'session_context.json', 'dice.json', 'model_calls.jsonl', 'runtime_errors.jsonl',
            'player_prompt_history.txt',
        ):
            (self.root / 'brain/state' / filename).unlink(missing_ok=True)
        receipts = self.root / 'brain/state/editor_receipts'
        if receipts.is_dir():
            for receipt in receipts.glob('*.json'):
                receipt.unlink(missing_ok=True)
        reset_state = {
            'schema_version': 1,
            'setup_status': 'new',
            'play_gate': 'setup_required',
            'position': {'day': 1, 'phase': PHASES[0], 'progress': 0.0},
            'pending_dice': None, 'pending_clarification': None,
            'day_end': None, 'pending_world_event': None, 'last_receipt': None,
            'draft': None, 'proposal': None, 'operation': None,
            'history': [], 'party': [], 'main_character': None,
            'game_cache': {}, 'saved_rolls': {}, 'specialist_proposals': {},
        }
        atomic_json(self.state.path, reset_state)
        self.state.append_event(
            'campaign_reset_started',
            previous_campaign_id=previous_campaign_id,
            position=reset_state['position'],
            status='in_progress',
        )

    def pause(self) -> dict[str, Any]:
        with runtime_lease(self.root):
            return self._pause_locked(self.state.load())

    def resume_play(self) -> dict[str, Any]:
        with runtime_lease(self.root):
            return self._resume_play_locked(self.state.load())

    def _pause_locked(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get('play_gate') != 'open':
            raise RuntimeError(f'Only open roleplay can be paused; current stage is {state.get("play_gate")}.')
        if state.get('operation'):
            raise RuntimeError('The current operation must finish before pausing roleplay.')
        self.state.save({'play_gate': 'paused', 'paused_from': 'open',
                         'message': 'Roleplay is paused outside the game. Use {resume} to continue.'})
        self.state.append_event(
            'gate_changed',
            operation_type='out_of_game',
            previous_gate='open',
            new_gate='paused',
            status='completed',
        )
        return self.view()

    def _resume_play_locked(self, state: dict[str, Any]) -> dict[str, Any]:
        gate = state.get('play_gate')
        if gate == 'world_event_pending':
            if not state.get('operation'):
                raise RuntimeError('The pending world event has no resumable operation.')
            self._drive()
            state = self.state.load()
            gate = state.get('play_gate')
        if gate == 'paused' or gate == 'new_day_pending':
            message = state.get('last_in_game_narration') or state.get('message') or 'Roleplay resumed.'
            self.state.save({'play_gate': 'open', 'paused_from': None, 'message': message})
            self.state.append_event(
                'gate_changed',
                operation_type='out_of_game',
                previous_gate=gate,
                new_gate='open',
                status='completed',
            )
            return self.view()
        if gate == 'new_game_pending':
            return self._start_opening(state)
        if gate == 'open':
            return self.view()
        raise RuntimeError(f'Roleplay cannot resume from runtime stage: {gate}')

    def review_current(self) -> dict[str, Any]:
        state = self.state.load()
        if state.get('play_gate') in {'setup_review', 'character_review', 'admin_review', 'day_end_review'}:
            # Re-display the current proposal file without rebuilding or
            # advancing the review cursor.
            return self.view()
        if state.get('play_gate') == 'day_end_pending':
            return self.prepare_day_end()
        return self.review_setup()

    def new_character(self) -> dict[str, Any]:
        return self._begin_character_mode('new_character')

    def new_party_member(self) -> dict[str, Any]:
        return self._begin_character_mode('new_party_member')

    def _begin_character_mode(self, mode: str) -> dict[str, Any]:
        from brain.setup_drafts import SetupDrafts
        with runtime_lease(self.root):
            SetupDrafts(self.state).begin(mode)
            return self.view()

    def add_character(self, identity: dict[str, Any], stats: dict[str, Any], description: str, character_class: str) -> dict[str, Any]:
        from brain.setup_drafts import SetupDrafts
        with runtime_lease(self.root):
            SetupDrafts(self.state).add(identity, stats, description, character_class)
            return self.view()

    def select_main(self, name: str) -> dict[str, Any]:
        from brain.setup_drafts import SetupDrafts
        with runtime_lease(self.root):
            SetupDrafts(self.state).choose(name)
            return self.view()

    def another_character(self) -> dict[str, Any]:
        from brain.setup_drafts import SetupDrafts
        with runtime_lease(self.root):
            SetupDrafts(self.state).another()
            return self.view()

    def cancel_setup(self) -> dict[str, Any]:
        from brain.setup_drafts import SetupDrafts
        with runtime_lease(self.root):
            SetupDrafts(self.state).cancel()
            return self.view()

    def undo_setup_input(self) -> dict[str, Any]:
        from brain.setup_drafts import SetupDrafts
        with runtime_lease(self.root):
            SetupDrafts(self.state).undo_last_input()
            return self.view()

    def cancel_pending(self) -> dict[str, Any]:
        """Cancel an unapplied review/proposal without changing campaign files."""
        with runtime_lease(self.root):
            state = self.state.load()
            if state['play_gate'] not in {'admin_review', 'day_end_review', 'setup_review', 'character_review', 'retry'}:
                raise RuntimeError('There is no pending operation to cancel.')
            draft = state.get('draft') or {}
            previous = draft.get('previous_gate') or (state.get('operation') or {}).get('return_gate') or 'open'
            self.state.save({'operation': None, 'proposal': None, 'pending_clarification': None,
                             'draft': None if draft else state.get('draft'), 'play_gate': previous,
                             'message': 'Pending operation cancelled; no campaign files were changed.'})
            self.state.append_event(
                'operation_cancelled',
                operation_id=(state.get('operation') or {}).get('id'),
                operation_type='out_of_game',
                previous_gate=state.get('play_gate'),
                restored_gate=previous,
                status='cancelled_by_player',
            )
            return self.view()

    def review_setup(self) -> dict[str, Any]:
        with runtime_lease(self.root):
            state = self.state.load()
            draft = state.get('draft') or {}
            if state['play_gate'] != 'setup_draft':
                raise RuntimeError('Start a character draft before review.')
            mode = draft.get('mode', 'new_game')
            if mode == 'new_game' and (not draft.get('main_character') or not draft.get('party_done')):
                raise RuntimeError('Finish the party and choose its main character before review.')
            if mode != 'new_game' and not draft.get('characters'):
                raise RuntimeError('Draft the character before review.')
            kind = 'setup' if mode == 'new_game' else 'character'
            stage = 'prepare_setup' if kind == 'setup' else 'prepare_character'
            operation = {'id': kind + '-' + uuid.uuid4().hex, 'kind': kind, 'stage': stage,
                         'operation_type': 'out_of_game', 'attempt_id': uuid.uuid4().hex, 'stage_run_id': uuid.uuid4().hex,
                         'before': state['position'], 'message': 'Prepare the character addition for review.', 'original_input': '/review',
                         'answers': [], 'revision': 0, 'results': {}, 'dice': {}}
            self.state.save({'operation': operation, 'play_gate': 'running'})
            self._journal_operation_event(
                'operation_started', operation,
                original_input=operation['message'],
                status='in_progress',
                stage=self._journal_stage(stage),
                position_before=state.get('position'),
            )
            return self._drive()

    def end_day(self) -> dict[str, Any]:
        with runtime_lease(self.root):
            self.require_open_play()
            state = self.state.load()
            self.state.save({'sleep_until_day': state['position']['day'] + 1, 'play_gate': 'sleep_pending'})
            return self._drive()

    def continue_run(self) -> dict[str, Any]:
        """Continue the exact saved checkpoint for internal recovery."""
        with runtime_lease(self.root):
            return self._drive()

    def retry(self) -> dict[str, Any]:
        """Retry only the most recently failed stage from its saved snapshot."""
        with runtime_lease(self.root):
            state = self.state.load()
            previous = state.get('operation')
            if state.get('play_gate') != 'retry' or not isinstance(previous, dict):
                raise RuntimeError('There is no failed task to retry.')
            operation_id = str(previous.get('id', ''))
            failed = self.state.latest_event(
                operation_id=operation_id,
                events={'stage_failed'},
            )
            if not isinstance(failed, dict):
                raise RuntimeError('The failed stage record is unavailable; state was left unchanged.')
            failed_run_id = failed.get('stage_run_id')
            started = next((item for item in reversed(self.state.journal_events(operation_id=operation_id))
                            if item.get('event') == 'stage_started' and item.get('stage_run_id') == failed_run_id), None)
            if not isinstance(started, dict) or not isinstance(started.get('snapshot'), dict):
                raise RuntimeError('The failed stage snapshot is unavailable; state was left unchanged.')
            snapshot = started['snapshot']
            saved_operation = snapshot.get('operation')
            if not isinstance(saved_operation, dict) or not saved_operation.get('message'):
                raise RuntimeError('The failed stage input is unavailable; state was left unchanged.')
            operation = {
                **saved_operation,
                'attempt_id': uuid.uuid4().hex,
                'stage_run_id': uuid.uuid4().hex,
                'revision': int(saved_operation.get('revision', 0) or 0) + 1,
            }
            restored = {
                **snapshot,
                'operation': operation,
                'play_gate': 'running',
                'pending_dice': snapshot.get('pending_dice'),
                'pending_clarification': None,
                'failure_reason': None,
                'message': f"Retrying {self._journal_stage(operation.get('stage'))} from its saved pre-stage state.",
            }
            self.state.replace(restored)
            self._journal_operation_event(
                'stage_retry_started',
                operation,
                attempt_id=operation.get('attempt_id'),
                retry_of=failed.get('event_id'),
                stage_run_id=operation.get('stage_run_id'),
                internal_stage=operation.get('stage'),
                stage=self._journal_stage(operation.get('stage')),
                previous_stage=self._journal_stage(operation.get('previous_stage')) if operation.get('previous_stage') else None,
                snapshot=restored,
                original_input=operation.get('message'),
                status='started',
            )
            self._journal_operation_event(
                'operation_restarted',
                operation,
                retry_of=failed.get('event_id'),
                stage=self._journal_stage(operation.get('stage')),
                status='in_progress',
            )
            return self._drive()

    def _context(self, operation: dict[str, Any]) -> dict[str, Any]:
        state = self.state.load()
        links = operation.get('clarification_links', [])
        if not isinstance(links, list):
            links = []
        active_link_id = operation.get('active_clarification_link_id')
        active_clarification = next(
            (link for link in reversed(links)
             if isinstance(link, dict) and link.get('id') == active_link_id and link.get('status') == 'answered'),
            None,
        )
        return {
            'turn_id': operation['id'], 'campaign_id': (state.get('draft') or {}).get('campaign_id', state.get('campaign_id', 'legacy')),
            'position': operation['before'], 'message': operation['message'],
            'answers': operation['answers'], 'history': state.get('history', []),
            'pending_clarification': state.get('pending_clarification') or operation.get('last_clarification'),
            'clarification_links': links, 'active_clarification': active_clarification,
            'game_cache': state.get('game_cache', {}), 'revision': operation['revision'],
            'review_proposal': state.get('proposal'), 'completed_day': state.get('completed_day'),
            'world_pool': state.get('world_pool'), 'review_kind': operation.get('review_gate'),
            'saved_rolls': state.get('saved_rolls', {}), 'draft': state.get('draft'),
            'event_to_encounter': operation.get('event_to_encounter'),
            'party': state.get('party', []), 'main_character': state.get('main_character'),
            'specialist_proposals': state.get('specialist_proposals', {}),
            'evidence_note': operation.get('evidence_note'),
            'internal_specialists': operation.get('internal_specialists', []),
            'setup_batches': operation.get('setup_batches', []),
        }

    @staticmethod
    def _journal_stage(stage: object) -> str:
        return JOURNAL_STAGE_NAMES.get(str(stage), str(stage))

    @staticmethod
    def _operation_type(operation: dict[str, Any]) -> str:
        return str(operation.get('operation_type') or ('out_of_game' if operation.get('is_admin') else 'gameplay'))

    def _journal_operation_event(self, event: str, operation: dict[str, Any], **fields: Any) -> None:
        self.state.append_event(
            event,
            operation_id=operation.get('id'),
            turn_id=operation.get('id') if self._operation_type(operation) == 'gameplay' else None,
            request_id=operation.get('id') if self._operation_type(operation) == 'out_of_game' else None,
            operation_type=self._operation_type(operation),
            **fields,
        )

    def _ensure_stage_started(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Create a durable pre-stage snapshot before any stage work runs."""
        state = self.state.load()
        current = state.get('operation')
        if not isinstance(current, dict):
            return operation
        operation = current
        changed = False
        if not operation.get('stage_run_id'):
            operation['stage_run_id'] = uuid.uuid4().hex
            self.state.save({'operation': operation})
            state = self.state.load()
            changed = True
        run_id = operation['stage_run_id']
        existing = self.state.latest_event(operation_id=operation.get('id'), events={'stage_started', 'stage_waiting'})
        if not changed and existing and existing.get('stage_run_id') == run_id and existing.get('internal_stage') == operation.get('stage'):
            return operation
        self._journal_operation_event(
            'stage_started',
            operation,
            attempt_id=operation.get('attempt_id', operation.get('id')),
            stage_run_id=run_id,
            internal_stage=operation.get('stage'),
            stage=self._journal_stage(operation.get('stage')),
            previous_stage=self._journal_stage(operation.get('previous_stage')) if operation.get('previous_stage') else None,
            original_input=operation.get('message'),
            snapshot=state,
            status='started',
        )
        return operation

    def _checkpoint(self, operation: dict[str, Any], stage: str, **changes: Any) -> None:
        journal_status = changes.pop('_journal_status', 'completed')
        completed_stage = operation.get('stage')
        completed_run_id = operation.get('stage_run_id')
        information = {
            'changes': changes,
            'results': operation.get('results', {}),
        }
        operation['previous_stage'] = completed_stage
        operation['stage'] = stage
        if journal_status == 'completed':
            operation['stage_run_id'] = uuid.uuid4().hex
        saved = self.state.save({'operation': operation, 'failure_reason': None, **changes})
        self._journal_operation_event(
            'stage_completed' if journal_status == 'completed' else 'stage_failed' if journal_status == 'failed' else 'stage_waiting',
            operation,
            attempt_id=operation.get('attempt_id', operation.get('id')),
            stage_run_id=completed_run_id,
            internal_stage=completed_stage,
            stage=self._journal_stage(completed_stage),
            next_stage=self._journal_stage(stage),
            information=information,
            snapshot=saved,
            status=journal_status,
        )
        if journal_status == 'completed':
            self._journal_operation_event(
                'stage_started',
                operation,
                attempt_id=operation.get('attempt_id', operation.get('id')),
                stage_run_id=operation.get('stage_run_id'),
                internal_stage=stage,
                stage=self._journal_stage(stage),
                previous_stage=self._journal_stage(completed_stage),
                original_input=operation.get('message'),
                snapshot=saved,
                status='started',
            )

    def _drive(self) -> dict[str, Any]:
        state = self.state.load()
        if not state.get('operation') and state['play_gate'] == 'sleep_pending':
            position = state['position']
            operation = {'id': 'rest-' + uuid.uuid4().hex, 'kind': 'turn', 'sleep': True, 'stage': 'route',
                         'operation_type': 'gameplay', 'attempt_id': uuid.uuid4().hex, 'stage_run_id': uuid.uuid4().hex,
                         'before': position,
                         'message': f"Rest only until the next phase boundary ({1 - position.get('progress', 0)} phase). Award only earned rest. Respect each NPC's explicit orders and sleep schedule; use AI decisions where no schedule exists. Stop if interrupted. Do not resolve the remainder of the night.",
                         'answers': [], 'revision': 0, 'results': {}, 'dice': {}}
            self.state.save({'operation': operation, 'play_gate': 'running'})
            self._journal_operation_event('operation_started', operation, original_input=operation['message'], status='in_progress', stage=self._journal_stage(operation['stage']), position_before=position)
            state = self.state.load()
        if not state.get('operation') or state['play_gate'] in {'awaiting_clarification', 'day_end_review', 'admin_review', 'setup_review', 'character_review'}:
            return self.view()
        operation = self._ensure_stage_started(state['operation'])
        state = self.state.load()
        operation = state['operation']
        context = self._context(operation)
        scope = {key: context[key] for key in ('campaign_id', 'turn_id', 'revision', 'position')}
        scope['state_version'] = state.get('state_version', 0)
        scope['source_hash'] = self._source_hash()
        try:
            with model_scope(self.root, scope):
                if operation['kind'] == 'apply':
                    self._apply(operation)
                elif operation['kind'] == 'setup':
                    prepared = self.modules.prepare_setup(context)
                    if prepared.get('batch_progress'):
                        operation['setup_batches'] = prepared['batch_progress']
                        self.state.save({'operation': operation})
                    if prepared.get('status') == 'needs_clarification':
                        if self._retry_internal(operation, prepared, context, role='admin'):
                            return self._drive()
                        self._hold_agent_clarification(prepared, operation, 'prepare_setup')
                    else:
                        if prepared.get('world_pool'):
                            self._validate_pool(prepared['world_pool'])
                            self.state.save({'world_pool': prepared['world_pool']})
                        self._prepare_review(prepared['proposal'], operation, 'setup_review')
                elif operation['kind'] == 'character':
                    proposal = self.modules.prepare_character_addition(context)
                    if proposal.get('status') == 'needs_clarification':
                        if self._retry_internal(operation, proposal, context, role='admin'):
                            return self._drive()
                        self._hold_agent_clarification(proposal, operation, 'prepare_character')
                    else:
                        self._prepare_review(proposal, operation, 'character_review')
                elif operation['kind'] == 'specialist':
                    proposal = self.modules.prepare_specialist_install(context, operation['specialist'])
                    self._prepare_review(proposal, operation, 'admin_review')
                elif operation['kind'] == 'day_end':
                    prepared = self.modules.prepare_day(context)
                    self._validate_pool(prepared['world_pool'])
                    operation['turn_ids'] = prepared.get('turn_ids', [])
                    self.state.save({'world_pool': prepared['world_pool']})
                    self._prepare_review(prepared['proposal'], operation, 'day_end_review')
                elif operation['kind'] == 'world':
                    self._world(operation)
                else:
                    self._turn(operation, context)
        except Exception as exc:
            # Never leak provider traces or hidden facts to the player. Record the
            # diagnostic privately so an operator can inspect a stuck step.
            try:
                error_path = self.root / 'brain/state/runtime_errors.jsonl'
                error_path.parent.mkdir(parents=True, exist_ok=True)
                with error_path.open('a', encoding='utf-8') as handle:
                    handle.write(json.dumps({
                        'campaign_id': scope.get('campaign_id'),
                        'operation': operation.get('id'),
                        'stage': operation.get('stage'),
                        'type': type(exc).__name__,
                        'error': str(exc),
                    }, ensure_ascii=False) + '\n')
            except OSError:
                pass
            safe_reason = str(exc).strip().replace('\n', ' ')
            if len(safe_reason) > 320:
                safe_reason = safe_reason[:317] + '...'
            failed_state = self.state.load()
            failed_operation_value = failed_state.get('operation')
            failed_operation: dict[str, Any] = failed_operation_value if isinstance(failed_operation_value, dict) else operation
            self._journal_operation_event(
                'stage_failed',
                failed_operation,
                attempt_id=failed_operation.get('attempt_id', failed_operation.get('id')),
                stage_run_id=failed_operation.get('stage_run_id'),
                internal_stage=failed_operation.get('stage'),
                stage=self._journal_stage(failed_operation.get('stage')),
                previous_stage=self._journal_stage(failed_operation.get('previous_stage')) if failed_operation.get('previous_stage') else None,
                snapshot=failed_state,
                status='failed',
                failure_reason=safe_reason or type(exc).__name__,
            )
            self.state.save({
                'play_gate': 'retry',
                'failure_reason': safe_reason or type(exc).__name__,
                'message': 'Processing stopped safely. Use /retry to resume this step.',
            })
            self._journal_operation_event(
                'operation_failed',
                failed_operation,
                stage=self._journal_stage(failed_operation.get('stage')),
                status='failed',
                failure_reason=safe_reason or type(exc).__name__,
            )
        return self.view()

    def _turn(self, operation: dict[str, Any], context: dict[str, Any]) -> None:
        results = operation['results']
        for _ in range(24):
            stage = operation['stage']
            if stage == 'route':
                route = self.modules.route(operation['message'], context)
                if route.get('preflight', {}).get('errors'):
                    raise RuntimeError('Routing preflight blocked.')
                route['turn_id'] = operation['id']
                results['route'] = route
                self._checkpoint(operation, 'evidence')
            elif stage == 'evidence':
                results['evidence'] = self.modules.evidence(results['route'], context, operation.get('evidence_note'))
                self._checkpoint(operation, 'specialists')
            elif stage == 'specialists':
                results['specialists'] = self.modules.specialists(results['evidence'], context)
                self._checkpoint(operation, 'admin' if results['route'].get('request_type') == 'admin' else 'resolve')
            elif stage == 'admin':
                response = self.modules.admin(results['evidence'], results['specialists'], context)
                if response.get('status') == 'proposal_ready':
                    self._prepare_review(response, operation, 'admin_review')
                elif response.get('status') == 'answered':
                    answer = response.get('answer', '')
                    self.state.save({'operation': None, 'play_gate': operation.get('return_gate', 'open'),
                                     'message': answer,
                                     'last_admin_diagnosis': response.get('diagnosis', {})})
                    self._journal_operation_event(
                        'operation_completed', operation,
                        stage='admin_operation_completed',
                        status='completed',
                        answer=answer,
                    )
                elif response.get('status') in {'needs_clarification', 'blocked'}:
                    if self._retry_internal(operation, response, context, role='admin'):
                        continue
                    self._hold_agent_clarification(response, operation, 'admin')
                else:
                    raise RuntimeError('Administrative analysis is incomplete.')
                return
            elif stage == 'resolve':
                lead = self.modules.resolve(results['specialists'], context, operation.get('dice_result'))
                lead['turn_id'] = operation['id']
                resolution = lead.get('resolution_record') or lead
                status = lead.get('status')
                if status == 'needs_clarification':
                    if self._retry_internal(operation, lead, context, role='lead'):
                        continue
                    question = lead.get('player_question') or resolution.get('clarification_request') or {'question': 'Please clarify your action.'}
                    self._hold_agent_clarification(lead, operation, 'resolve', question=question)
                    return
                if status == 'awaiting_dice':
                    request = resolution.get('dice_request') or {}
                    self._roll(operation, request)
                    continue
                if status == 'blocked':
                    if self._retry_internal(operation, lead, context, role='lead'):
                        continue
                    if lead.get('evidence_expansion_request'):
                        self._hold_agent_clarification(lead, operation, 'resolve')
                        return
                    raise RuntimeError('Resolution is not complete.')
                if status != 'resolved':
                    raise RuntimeError('Resolution is not complete.')
                after, transitions = self._time(operation['before'], lead)
                if operation.get('sleep'):
                    if len(transitions) > 1 or (len(transitions) == 1 and after.get('progress', 0)):
                        raise RuntimeError('Rest must stop at the next phase boundary.')
                    if after == operation['before'] and not resolution.get('interrupted'):
                        raise RuntimeError('Rest must advance time or explicitly interrupt.')
                event = self.state.load().get('pending_world_event')
                if event and self._event_due(event, after) and not operation.get('event_to_encounter'):
                    operation['event_to_encounter'] = event
                    context['event_to_encounter'] = event
                    self._checkpoint(operation, 'resolve')
                    continue
                if operation.get('event_to_encounter'):
                    # The runtime owns encounter bookkeeping; the model staged
                    # the scene above, so mark the due event as encountered.
                    resolution['encountered_event_id'] = operation['event_to_encounter']['id']
                results.update(resolution=lead, after=after, transitions=transitions)
                self._checkpoint(operation, 'narrate')
                self._start_background(operation, context)
            elif stage == 'narrate':
                self._start_background(operation, context)
                results['narration'] = self.modules.narrate(results['resolution'], context)
                self._checkpoint(operation, 'record')
            elif stage == 'record':
                results['record'] = self.modules.record(results['resolution'], {**context, 'position': results['after']})
                self._checkpoint(operation, 'background', message=results['narration']['narration'])
            elif stage == 'time':
                after, transitions = self._time(operation['before'], results['resolution'])
                results['after'] = after
                results['transitions'] = transitions
                self._checkpoint(operation, 'background')
            elif stage == 'background':
                if results['transitions']:
                    self._start_background(operation, context)
                    future = self._background[operation['id']]
                    result = future.result()
                    if result.get('status') not in {'complete', 'no_tick_required', 'interrupted'}:
                        self._background.pop(operation['id'], None)
                        raise RuntimeError('Background work remains unresolved.')
                    results['background'] = result
                    self._background.pop(operation['id'], None)
                self._checkpoint(operation, 'finish')
            elif stage == 'finish':
                state = self.state.load()
                after = results['after']
                interruption = results.get('background', {}).get('interrupt') or {}
                if interruption and (interruption.get('visibility') not in {'visible', 'public'} or not isinstance(interruption.get('message'), str)):
                    raise RuntimeError('Interruptions require an explicitly player-visible report.')
                interrupted = bool(interruption) or bool((results['resolution'].get('resolution_record') or {}).get('interrupted'))
                message = results['narration']['narration'] + ('\n' + interruption['message'] if interruption else '')
                keep_sleeping = operation.get('sleep') and not interrupted and after['day'] < state.get('sleep_until_day', after['day'])
                crossed_day = after['day'] > operation['before']['day']
                review_due = crossed_day or state.get('review_after_interrupt', False)
                gate = 'sleep_pending' if keep_sleeping else 'day_end_pending' if review_due and not interrupted else 'open'
                history = [*state.get('history', []), {'turn_id': operation['id'], 'day': operation['before']['day'], 'prompt': operation['message'], 'result': message}]
                created = (results.get('specialists') or {}).get('specialist_updates', {}).get('created_specialists') or []
                specialist_proposals = {**state.get('specialist_proposals', {}), **{p['name']: p for p in created if isinstance(p, dict) and p.get('name')}}
                self.state.save({
                    'position': after, 'history': history, 'operation': None,
                    'play_gate': gate, 'sleep_until_day': state.get('sleep_until_day') if keep_sleeping else None,
                    'review_after_interrupt': review_due and interrupted,
                    'last_in_game_narration': message,
                    'message': message, 'state_version': state.get('state_version', 0) + 1,
                    'game_cache': results['record'].get('cache_delta') or state.get('game_cache', {}),
                    'pending_dice': None, 'pending_clarification': None,
                    'completed_day': operation['before']['day'] if after['day'] > operation['before']['day'] else state.get('completed_day'),
                    'saved_rolls': {**state.get('saved_rolls', {}), operation['id']: operation['dice']},
                    'pending_world_event': None if operation.get('event_to_encounter') else state.get('pending_world_event'),
                    'specialist_proposals': specialist_proposals,
                })
                self._journal_operation_event(
                    'operation_completed', operation,
                    stage='recorder',
                    position_after=after,
                    status='completed',
                    result=message,
                )
                return
            else:
                raise RuntimeError('Unknown saved stage.')
        raise RuntimeError('Continuation limit reached; requires review.')

    def _retry_internal(self, operation: dict[str, Any], response: dict[str, Any], context: dict[str, Any], *, role: str) -> bool:
        """Give internal evidence and specialist lanes a bounded second chance."""
        resolution_value = response.get('resolution_record')
        resolution: dict[str, Any] = resolution_value if isinstance(resolution_value, dict) else {}
        diagnosis_value = response.get('diagnosis')
        diagnosis: dict[str, Any] = diagnosis_value if isinstance(diagnosis_value, dict) else {}
        if not diagnosis and isinstance(response.get('result_reason'), dict):
            diagnosis = dict(response['result_reason'])
        clarification = response.get('clarification_request') if isinstance(response.get('clarification_request'), dict) else resolution.get('clarification_request')
        if isinstance(clarification, dict):
            diagnosis = {**diagnosis, **clarification}
        expansion_value = response.get('evidence_expansion_request')
        expansion: dict[str, Any] = expansion_value if isinstance(expansion_value, dict) else {}
        internal_search = bool(diagnosis.get('internal_search')) or bool(expansion)
        request = str(diagnosis.get('evidence_request') or expansion.get('evidence_note') or '').strip()
        if not internal_search or not request:
            return False
        round_key = f'{role}_internal_round'
        round_number = int(operation.get(round_key, 0) or 0)
        if round_number >= 2:
            return False
        specialists = diagnosis.get('specialists', [])
        if not isinstance(specialists, list):
            specialists = []
        operation[round_key] = round_number + 1
        operation['evidence_note'] = (
            f'{role.title()} reported an unresolved issue: {diagnosis.get("issue", "internal information is missing")}.\n'
            f'Why it matters: {diagnosis.get("why", "the result is not yet defensible")}.\n'
            f'Internal evidence request: {request}'
        )
        operation['internal_specialists'] = [str(item) for item in specialists if isinstance(item, str)]
        context['internal_specialists'] = operation['internal_specialists']
        operation['results'].pop('evidence', None)
        operation['results'].pop('specialists', None)
        if role == 'lead':
            operation['results'].pop('resolution', None)
        self._checkpoint(operation, 'evidence')
        return True

    def _hold_agent_clarification(
        self,
        response: dict[str, Any],
        operation: dict[str, Any],
        stage: str,
        *,
        question: Any = None,
    ) -> None:
        diagnosis = response.get('diagnosis') if isinstance(response.get('diagnosis'), dict) else {}
        reason = response.get('result_reason') if isinstance(response.get('result_reason'), dict) else {}
        expansion = response.get('evidence_expansion_request') if isinstance(response.get('evidence_expansion_request'), dict) else {}
        if not diagnosis and expansion:
            diagnosis = {
                'issue': 'Required internal evidence is still unresolved.',
                'why': expansion.get('evidence_note') or 'The available specialist evidence was not sufficient for a defensible result.',
                'player_question': '',
            }
        candidate: dict[str, Any] = dict(response)
        if isinstance(question, dict):
            candidate.update(question)
        presented = PlayerClarification.present(candidate)
        if not presented:
            self._checkpoint(
                operation, stage, play_gate='retry', pending_clarification=None,
                message='The game is resolving an internal evidence question; no private backend details are required from the player.',
                _journal_status='failed',
            )
            return
        operation['stage'] = stage
        question_payload = {
            **presented,
            'source': 'admin_agent' if stage in {'admin', 'prepare_setup', 'prepare_character'} else 'lead_resolver',
        }
        links = operation.setdefault('clarification_links', [])
        link_id = f"{operation.get('id', 'operation')}:clarification:{len(links) + 1}"
        question_payload['link_id'] = link_id
        links.append({
            'id': link_id,
            'source': question_payload['source'],
            'stage': stage,
            'question': question_payload.get('question', ''),
            'result': response,
            'answer': None,
            'status': 'awaiting_answer',
            'requested_revision': int(operation.get('revision', 0) or 0),
        })
        operation['active_clarification_link_id'] = link_id
        self._checkpoint(
            operation, stage, play_gate='awaiting_clarification',
            pending_clarification=question_payload,
            _journal_status='awaiting_clarification',
        )
        self._journal_operation_event(
            'clarification_requested', operation,
            stage=self._journal_stage(stage),
            question=question_payload,
            status='awaiting_clarification',
        )

    def _start_background(self, operation: dict[str, Any], context: dict[str, Any]) -> None:
        if not operation['results'].get('transitions'):
            return
        prior = self._background.get(operation['id'])
        if prior is not None and not (prior.done() and prior.exception()):
            return
        hidden_context = {**context, 'foreground_resolution': operation['results']['resolution']}
        metadata = {'campaign_id': context['campaign_id'], 'turn_id': operation['id'], 'revision': context['revision'], 'visibility': 'private', 'source_hash': self._source_hash()}
        def work() -> dict[str, Any]:
            with model_scope(self.root, metadata):
                return self.modules.background(operation['results']['transitions'], hidden_context)
        self._background[operation['id']] = self._executor.submit(copy_context().run, work)

    def close_session(self) -> None:
        with runtime_lease(self.root):
            state = self.state.load()
            self.state.append_event(
                'session_closed',
                operation_id=(state.get('operation') or {}).get('id') if isinstance(state.get('operation'), dict) else None,
                play_gate=state.get('play_gate'),
                position=state.get('position'),
                status='completed',
            )

    def close(self) -> None:
        self._executor.shutdown(wait=True)

    def _review_question(self, message: str, state: dict[str, Any]) -> dict[str, Any]:
        operation = state['operation']
        context = {**self._context(operation), 'message': message + '\nRead-only question about the pending proposal. Do not propose or apply edits.'}
        with model_scope(self.root, {'campaign_id': context['campaign_id'], 'turn_id': operation['id'], 'revision': operation['revision'], 'source_hash': self._source_hash(), 'visibility': 'player'}):
            route = self.modules.route(context['message'], context)
            route['turn_id'] = operation['id'] + '-query-' + uuid.uuid4().hex
            bundle = self.modules.evidence(route, context)
            analysis = self.modules.specialists(bundle, context)
            answer = self.modules.admin(bundle, analysis, context)
        # Queries cannot replace or implicitly revise the pending proposal.
        self.state.save({'message': answer.get('answer', 'Please submit revisions without braces.')})
        return self.view()

    def _revise(self, message: str, state: dict[str, Any]) -> dict[str, Any]:
        operation = state['operation']
        operation.pop('approved', None)
        operation.pop('receipt', None)
        operation['revision'] += 1
        operation['answers'].append(message)
        operation['stage_run_id'] = uuid.uuid4().hex
        operation['results'] = {}
        self._journal_operation_event(
            'proposal_revision_received', operation,
            exact_input=message,
            status='in_progress',
        )
        if state['play_gate'] == 'setup_review':
            operation.pop('setup_batches', None)
        gate = state['play_gate']
        operation['kind'] = 'day_end' if gate == 'day_end_review' else 'setup' if gate == 'setup_review' else 'turn'
        operation['stage'] = 'prepare_day' if gate == 'day_end_review' else 'prepare_setup' if gate == 'setup_review' else 'route'
        if gate == 'admin_review':
            operation['message'] = '{Revise the entire pending proposal, checking rules and dependent outcomes. ' + message + '}'
        self.state.save({'operation': operation, 'play_gate': 'running', 'message': 'Rechecking the revised proposal.'})
        return self._drive()

    def _hold_clarification(self, response: dict[str, Any], operation: dict[str, Any], stage: str) -> None:
        """Expose only a safe player question; internal failures are retried."""
        state = self.state.load()
        draft = state.get('draft') or {}
        fallback = None
        if stage == 'prepare_setup' and draft.get('mode') == 'new_game':
            fallback = PlayerClarification.from_setup_draft(draft)
        if fallback is None and stage == 'prepare_character':
            fallback = 'Please provide the missing player-facing detail for this character.'
        presented = PlayerClarification.present(response, fallback=fallback)
        operation['stage'] = stage
        if not presented:
            self._checkpoint(
                operation, stage, play_gate='retry', pending_clarification=None,
                message='The game is rechecking the setup proposal; no private file or rule details are required from the player.',
                _journal_status='failed',
            )
            return
        question_payload = {**presented, 'source': 'setup'}
        links = operation.setdefault('clarification_links', [])
        link_id = f"{operation.get('id', 'operation')}:clarification:{len(links) + 1}"
        question_payload['link_id'] = link_id
        links.append({
            'id': link_id,
            'source': 'setup',
            'stage': stage,
            'question': question_payload.get('question', ''),
            'result': response,
            'answer': None,
            'status': 'awaiting_answer',
            'requested_revision': int(operation.get('revision', 0) or 0),
        })
        operation['active_clarification_link_id'] = link_id
        self._checkpoint(
            operation, stage, play_gate='awaiting_clarification',
            pending_clarification=question_payload,
            _journal_status='awaiting_clarification',
        )
        self._journal_operation_event(
            'clarification_requested', operation,
            stage=self._journal_stage(stage),
            question=question_payload,
            status='awaiting_clarification',
        )

    def _prepare_review(self, proposal: dict[str, Any], operation: dict[str, Any], gate: str) -> None:
        from brain.game_modules import admin_module
        proposal = {**proposal, 'status': 'proposal_ready',
                    'proposal_id': operation['id'] + '-v' + str(operation['revision']),
                    # Every campaign Markdown proposal crosses the Admin Agent
                    # boundary before it can be version-bound or approved.
                    'proposed_by': proposal.get('proposed_by', 'admin_agent')}
        bound = admin_module('approval').bind_source_versions(proposal, repo_root=self.root)
        self.state.save({'proposal': bound, 'proposal_file_index': 0, 'operation': operation, 'play_gate': gate, 'message': 'Review the proposed campaign records one file at a time.', 'pending_clarification': None})
        self._journal_operation_event(
            'proposal_created', operation,
            proposal_id=bound.get('proposal_id'),
            stage='proposal_or_answer',
            status='awaiting_approval',
            proposed_files=[change.get('target_file') for change in bound.get('changes', []) if isinstance(change, dict)],
        )

    def next_proposal_file(self) -> dict[str, Any]:
        with runtime_lease(self.root):
            state = self.state.load()
            if state.get('play_gate') not in {'setup_review', 'character_review', 'admin_review', 'day_end_review'}:
                raise RuntimeError('There is no proposal being reviewed.')
            proposal_for_total_value = state.get('proposal')
            proposal_for_total: dict[str, Any] = proposal_for_total_value if isinstance(proposal_for_total_value, dict) else {}
            total = sum(
                1 for change in proposal_for_total.get('changes', [])
                if isinstance(change, dict) and str(change.get('target_file', '')).startswith('markdown_files/')
            )
            index = state.get('proposal_file_index', 0)
            index = index if isinstance(index, int) and index >= 0 else 0
            next_index = min(index + 1, total)
            self.state.save({'proposal_file_index': next_index})
            operation_value = state.get('operation')
            operation: dict[str, Any] = operation_value if isinstance(operation_value, dict) else {}
            proposal_value = state.get('proposal')
            proposal: dict[str, Any] = proposal_value if isinstance(proposal_value, dict) else {}
            changes = [change for change in proposal.get('changes', []) if isinstance(change, dict)]
            reviewed = changes[index] if index < len(changes) else {}
            self._journal_operation_event(
                'proposal_file_reviewed', operation,
                proposal_id=proposal.get('proposal_id'),
                filename=reviewed.get('target_file'),
                file_number=index + 1,
                review_position_before=index,
                review_position_after=next_index,
                status='completed',
            )
            return self.view()

    def approve(self, *, confirm_reset: bool = False) -> dict[str, Any]:
        from brain.game_modules import admin_module
        with runtime_lease(self.root):
            state = self.state.load()
            if state['play_gate'] not in {'admin_review', 'day_end_review', 'setup_review', 'character_review'} or not state.get('proposal'):
                raise RuntimeError('There is no proposal awaiting approval.')
            if state['play_gate'] == 'setup_review' and not confirm_reset:
                raise ValueError('Replacement requires explicit confirmation: /approve-reset.')
            operation = state['operation']
            operation['approved'] = admin_module('approval').approve_proposal(state['proposal'])
            operation['review_gate'] = state['play_gate']
            operation['kind'] = 'apply'
            operation['operation_type'] = 'out_of_game'
            self._journal_operation_event(
                'approval_requested', operation,
                proposal_id=state['proposal'].get('proposal_id'),
                approval_type='full_campaign_replacement' if state['play_gate'] == 'setup_review' else 'campaign_change',
                status='in_progress',
            )
            self._checkpoint(operation, 'apply', play_gate='running')
            return self._drive()

    def _apply(self, operation: dict[str, Any]) -> None:
        from brain.game_modules import admin_module
        if operation['stage'] == 'apply':
            receipt = admin_module('admin_editor').AdminEditor(self.root).apply(operation['approved'])
            if receipt.get('status') != 'applied':
                self.state.save({'play_gate': operation['review_gate'], 'message': 'Changes were not applied. Review or retry the proposal.'})
                return
            operation['receipt'] = receipt
            self._checkpoint(operation, 'reconcile')
        if hasattr(self.modules, 'reconcile'):
            self.modules.reconcile(operation, self._context(operation))
        if hasattr(self.modules, 'refresh'):
            self.modules.refresh()
        if operation.get('review_gate') == 'day_end_review' and hasattr(self.modules, 'discover_branches'):
            discovery = self.modules.discover_branches(self._context(operation))
            if hasattr(self.modules, 'refresh'):
                self.modules.refresh()
            self.state.save({'branch_discovery': discovery})
        state = self.state.load()
        self.state.save({'proposal': None, 'last_receipt': operation['receipt'],
                         'message': 'Approved changes saved.', 'state_version': state.get('state_version', 0) + 1})
        if operation['review_gate'] == 'setup_review':
            self._activate_setup(operation)
        elif operation['review_gate'] == 'character_review':
            self._activate_character(operation)
        elif operation['review_gate'] == 'day_end_review':
            operation['kind'] = 'world'
            self._checkpoint(operation, 'world', play_gate='world_event_pending')
            self._world(operation)
        else:
            return_gate = operation.get('return_gate', 'open')
            if return_gate not in self.OUTSIDE_PLAY_GATES:
                return_gate = 'open'
            final_message = 'Administrative changes saved; roleplay remains paused outside the game.' if return_gate in self.OUTSIDE_PLAY_GATES else 'Administrative changes saved.'
            self.state.save({'operation': None, 'play_gate': return_gate, 'message': final_message})
            self._journal_operation_event(
                'operation_completed', operation,
                stage='admin_operation_completed',
                status='completed',
                receipt=operation.get('receipt'),
                message=final_message,
            )

    def _activate_character(self, operation: dict[str, Any]) -> None:
        state = self.state.load()
        draft = state['draft']
        character = draft['characters'][0]
        party = [*(state.get('party') or []), character]
        message = draft.get('previous_message') or state.get('last_in_game_narration') or 'Character added to the party.'
        self.state.save({
            'party': party, 'draft': None, 'operation': None, 'proposal': None,
            'play_gate': 'open', 'message': message,
            'last_receipt': operation['receipt'],
            'state_version': state.get('state_version', 0) + 1,
        })
        self._journal_operation_event(
            'operation_completed', operation,
            stage='admin_operation_completed',
            status='completed',
            message=message,
        )

    def specialist_proposals(self) -> list[dict[str, Any]]:
        with runtime_lease(self.root):
            return list((self.state.load().get('specialist_proposals') or {}).values())

    def propose_specialist(self, name: str) -> dict[str, Any]:
        with runtime_lease(self.root):
            state = self.state.load()
            if state['play_gate'] != 'open':
                raise RuntimeError('Install specialists between turns, when play is open.')
            stored = (state.get('specialist_proposals') or {}).get(name)
            if not isinstance(stored, dict):
                raise ValueError('No stored specialist proposal by that name.')
            operation = {'id': 'specialist-' + uuid.uuid4().hex, 'kind': 'specialist', 'stage': 'prepare_specialist',
                         'operation_type': 'out_of_game', 'attempt_id': uuid.uuid4().hex, 'stage_run_id': uuid.uuid4().hex,
                         'before': state['position'], 'message': f'Install specialist {name}.', 'original_input': f'/install {name}',
                         'answers': [], 'revision': 0, 'results': {}, 'dice': {}, 'specialist': stored}
            self.state.save({'operation': operation, 'play_gate': 'running'})
            self._journal_operation_event('operation_started', operation, original_input=operation['message'], status='in_progress', stage=self._journal_stage(operation['stage']), position_before=state.get('position'))
            return self._drive()

    def _activate_setup(self, operation: dict[str, Any]) -> None:
        from brain.persistence import atomic_text
        state = self.state.load()
        draft = state['draft']
        # The editor receipt already committed replacement documents. This
        # private activation is replayable until the opening operation is saved.
        journal = self.root / 'brain/state/model_calls.jsonl'
        if journal.exists():
            retained = []
            for line in journal.read_text(encoding='utf-8').splitlines():
                item = json.loads(line)
                if item.get('metadata', {}).get('campaign_id') == draft['campaign_id']:
                    retained.append(line)
            atomic_text(journal, '\n'.join(retained) + ('\n' if retained else ''))
        for name in ('background_state.json', 'background_visible.md', 'pipeline_cache.json', 'session_context.json', 'dice.json'):
            (self.root / 'brain/state' / name).unlink(missing_ok=True)
        self.state.save({'campaign_id': draft['campaign_id'], 'main_character': draft['main_character'], 'party': draft['characters'],
                         'draft': None, 'setup_status': 'active', 'position': {'day': 1, 'phase': PHASES[0], 'progress': 0}, 'operation': None,
                         'history': [], 'game_cache': {}, 'saved_rolls': {}, 'pending_world_event': None,
                         'world_pool': state.get('world_pool'),
                         'completed_day': None, 'pending_dice': None, 'pending_clarification': None, 'day_end': None,
                         'play_gate': 'new_game_pending', 'paused_from': 'new_game_pending',
                         'message': 'Setup changes are stored. Review them, then use {resume} to begin roleplay.'})
        self._journal_operation_event(
            'operation_completed', operation,
            stage='admin_operation_completed',
            status='completed',
            message='New campaign setup applied.',
        )

    def _start_opening(self, state: dict[str, Any]) -> dict[str, Any]:
        draft = state.get('draft') or {}
        campaign_id = state.get('campaign_id') or draft.get('campaign_id')
        if not campaign_id:
            raise RuntimeError('Cannot start roleplay without an approved campaign.')
        opening = {'id': 'opening-' + campaign_id, 'kind': 'turn', 'stage': 'route',
                   'operation_type': 'gameplay', 'attempt_id': uuid.uuid4().hex, 'stage_run_id': uuid.uuid4().hex,
                   'before': {'day': 1, 'phase': PHASES[0], 'progress': 0},
                   'message': 'Begin the approved new campaign. Design the first scenario from the saved party backgrounds and established world lore. Introduce the situation without deciding the player response. No time elapses for this introduction.',
                   'answers': [], 'revision': 0, 'results': {}, 'dice': {}, 'return_gate': 'open'}
        self.state.save({'operation': opening, 'play_gate': 'running', 'paused_from': None,
                         'message': 'Beginning the approved campaign.'})
        self._journal_operation_event('operation_started', opening, original_input=opening['message'], status='in_progress', stage=self._journal_stage(opening['stage']), position_before=opening['before'])
        self._drive()
        return self.view()

    def _event_due(self, event: dict[str, Any], position: dict[str, Any]) -> bool:
        if position['day'] > event['day']:
            return True
        if position['day'] < event['day']:
            return False
        if PHASES.index(position['phase']) >= PHASES.index(event['latest_phase']):
            return True
        condition = event.get('encounter_condition')
        # Structured conditions can trigger earlier; free-text conditions always
        # have a deterministic deadline fallback rather than guessing intent.
        if isinstance(condition, dict) and condition.get('location'):
            return condition['location'] == self.state.load().get('location')
        return False

    @staticmethod
    def _validate_pool(pool: Any) -> None:
        if not isinstance(pool, dict) or not pool or any(not isinstance(values, list) for values in pool.values()):
            raise ValueError('World trigger pool must contain explicit number lists.')
        values = [number for numbers in pool.values() for number in numbers]
        if any(type(number) is not int for number in values) or sorted(values) != list(range(1, 101)):
            raise ValueError('World pool must own every number 1–100 exactly once.')

    def prepare_day_end(self) -> dict[str, Any]:
        with runtime_lease(self.root):
            state = self.state.load()
            if state['play_gate'] != 'day_end_pending':
                raise RuntimeError('The current day has not finished.')
            operation = {'id': 'day-end-' + uuid.uuid4().hex, 'kind': 'day_end', 'stage': 'prepare_day',
                         'before': state['position'], 'message': 'Prepare the completed day for review.', 'answers': [],
                         'revision': 0, 'results': {}, 'dice': {}}
            self.state.save({'operation': operation, 'play_gate': 'running'})
            return self._drive()

    def _world(self, operation: dict[str, Any]) -> None:
        state = self.state.load()
        pool = state['world_pool']
        self._validate_pool(pool)
        if 'world_roll' not in operation:
            identity = self._context(operation)['campaign_id'] + '/world/' + str(state['position']['day'])
            operation['world_roll'] = DiceJournal(self.root).roll(identity, sides=100)['result']
            self._checkpoint(operation, 'world', play_gate='world_event_pending')
        roll = operation['world_roll']
        owner = next(name for name, numbers in pool.items() if roll in numbers)
        if owner.casefold() == 'nothing':
            # The established rules explicitly allow this category. Never reroll
            # or fabricate an event to disguise that rule-defined result.
            self.state.save({'pending_world_event': None, 'operation': None, 'play_gate': 'new_day_pending', 'proposal': None,
                             'paused_from': 'new_day_pending',
                             'last_world_check': {'day': state['position']['day'], 'roll': roll, 'trigger': owner},
                             'message': 'Day-end changes are stored. Review complete; use {resume} to begin the next day.'})
            return
        event = self.modules.world(self._context(operation), roll, pool)
        if event.get('roll') != roll or event.get('selected_trigger') != owner:
            raise ValueError('World event does not match the saved roll and frozen pool.')
        if not event.get('encounter_condition') or event.get('latest_phase') not in PHASES or not event.get('generated_event'):
            raise ValueError('World event is missing its setup, encounter condition, or deadline.')
        event = {**event, 'id': 'event-' + operation['id'], 'day': state['position']['day'], 'status': 'pending'}
        self.state.save({'pending_world_event': event, 'operation': None, 'play_gate': 'new_day_pending', 'proposal': None,
                         'paused_from': 'new_day_pending',
                         'message': 'Day-end changes are stored. Review complete; use {resume} to begin the next day.'})

    def _roll(self, operation: dict[str, Any], request: dict[str, Any]) -> None:
        sides = request.get('sides', 20)
        count = request.get('count', 1)
        if not isinstance(sides, int) or not 2 <= sides <= 100 or not isinstance(count, int) or not 1 <= count <= 20:
            raise ValueError('Invalid dice request.')
        key = str(request.get('roll_id', 'action'))
        if key in operation['dice']:
            saved = operation['dice'][key]
            if saved['sides'] != sides or saved['count'] != count:
                raise ValueError('A saved roll cannot change shape.')
            if operation.get('dice_result') == saved:
                raise RuntimeError('Resolver requested an already supplied roll.')
        else:
            identity = self._context(operation)['campaign_id'] + '/' + operation['id'] + '/' + key
            operation['dice'][key] = DiceJournal(self.root).roll(identity, sides=sides, count=count)
        operation['dice_result'] = operation['dice'][key]
        self._checkpoint(operation, 'resolve', pending_dice=operation['dice_result'])

    @staticmethod
    def _phase_distance(current: Any, target: Any) -> float:
        return (target.day - current.day) * len(PHASES) + (PHASES.index(target.phase) - PHASES.index(current.phase))

    @staticmethod
    def _elapsed_phases(change: dict[str, Any], current: Any, clock: PhaseClock) -> float:
        for key in ('elapsed_phases', 'delta_phases', 'phases_elapsed', 'phases', 'phase_cost', 'time_consumed'):
            value = change.get(key)
            if value is None or isinstance(value, bool):
                continue
            if isinstance(value, str):
                match = re.search(r'(\d+(?:\.\d+)?)', value)
                if not match:
                    continue
                value = match.group(1)
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        to = change.get('to')
        if isinstance(to, dict) and to.get('phase') is not None and to.get('day') is not None:
            try:
                raw_progress = float(to.get('progress', 0))
            except (TypeError, ValueError):
                raw_progress = 0.0
            if int(to['day']) == current.day and to['phase'] == current.phase and 0 < raw_progress < 1:
                return raw_progress
            if raw_progress >= 1.0:
                return raw_progress
            try:
                return CampaignPipeline._phase_distance(current, clock.position(int(to['day']), to['phase'], 0.0))
            except ValueError:
                pass
        after_phase = change.get('after_phase') or change.get('ending_phase') or change.get('phase')
        after_day = change.get('after_day', change.get('day'))
        if after_phase and after_day is not None and after_phase != current.phase:
            try:
                return CampaignPipeline._phase_distance(current, clock.position(int(after_day), after_phase, 0.0))
            except ValueError:
                pass
        return 0.0

    @staticmethod
    def _time(before: dict[str, Any], lead: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        clock = PhaseClock()
        start = clock.position(before['day'], before['phase'], before.get('progress', 0))
        current = start
        transitions: list[dict[str, Any]] = []
        for change in (lead.get('resolution_record') or lead).get('time_changes', []):
            if not isinstance(change, dict):
                continue
            elapsed = CampaignPipeline._elapsed_phases(change, current, clock)
            if elapsed <= 0:
                continue
            if not math.isfinite(elapsed) or elapsed > 9:
                raise ValueError('Invalid duration; multi-day actions require separate daily gates.')
            steps = clock.advance(current, elapsed)
            total = current.progress + elapsed
            base = steps[-1].current if steps else current
            after = clock.position(base.day, base.phase, round(total % 1, 8))
            if after.day > start.day + 1 or (after.day > start.day and (after.phase != PHASES[0] or after.progress)):
                raise ValueError('An action must stop at the next daily review gate.')
            transitions.extend(step.to_dict() for step in steps)
            current = after
        return current.to_dict(), transitions

    def _source_hash(self) -> str:
        digest = hashlib.sha256()
        for path in sorted((self.root / 'markdown_files').glob('*.md')):
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def require_open_play(self) -> None:
        gate = self.state.load()['play_gate']
        if gate != 'open':
            raise RuntimeError(f'Play is blocked by runtime stage: {gate}')
