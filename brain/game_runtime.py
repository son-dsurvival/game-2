"""Resumable orchestration. Terminal IO and model implementations live elsewhere."""
from __future__ import annotations

import hashlib
import json
import math
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
from typing import Any

from backend.phase_clock import PHASES, PhaseClock
from brain.model_gateway import model_scope
from brain.dice import DiceJournal
from brain.persistence import runtime_lease
from brain.runtime_state import RuntimeStateStore


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
            return self.view()

    def view(self) -> dict[str, Any]:
        state = self.state.load()
        operation = state.get('operation') or {}
        result = {
            'status': state['play_gate'], 'play_gate': state['play_gate'],
            'position': state['position'], 'message': state.get('message', ''),
            'turn_id': operation.get('id'), 'stage': operation.get('stage'),
        }
        if state.get('draft'):
            result['draft'] = {key: value for key, value in state['draft'].items() if key != 'previous_gate'}
        if state.get('pending_clarification'):
            result['question'] = state['pending_clarification']
        if state.get('proposal'):
            result['proposal'] = state['proposal']
        return result

    def submit(self, message: str) -> dict[str, Any]:
        if not message.strip():
            raise ValueError('Enter a message.')
        with runtime_lease(self.root):
            state = self.state.load()
            if state.get('operation') and state['play_gate'] in {'running', 'retry', 'background_pending'}:
                self._drive()
                state = self.state.load()
            if state['play_gate'] in {'day_end_review', 'setup_review', 'admin_review'}:
                if message.strip().startswith('{') and message.strip().endswith('}'):
                    return self._review_question(message, state)
                return self._revise(message, state)
            if state['play_gate'] == 'setup_draft':
                from brain.setup_drafts import SetupDrafts
                SetupDrafts(self.state).answer(message)
                return self.view()
            if state['play_gate'] == 'awaiting_clarification':
                operation = state['operation']
                operation['answers'].append(message)
                operation['revision'] += 1
                operation['stage'] = 'evidence'
                for key in ('evidence', 'specialists', 'resolution'):
                    operation['results'].pop(key, None)
                self.state.save({'operation': operation, 'pending_clarification': None, 'play_gate': 'running'})
            else:
                is_admin = message.strip().startswith('{') and message.strip().endswith('}')
                if not is_admin:
                    self.require_open_play()
                elif state['play_gate'] not in {'open', 'day_end_review', 'admin_review'}:
                    raise RuntimeError('Finish or resume the pending operation before administrative edits.')
                operation = {
                    'id': 'turn-' + uuid.uuid4().hex, 'kind': 'turn', 'stage': 'route',
                    'message': message, 'answers': [], 'revision': 0, 'results': {},
                    'before': state['position'], 'dice': {}, 'return_gate': state['play_gate'],
                }
                self.state.save({'operation': operation, 'play_gate': 'running', 'message': ''})
            return self._drive()

    def begin_setup(self) -> dict[str, Any]:
        from brain.setup_drafts import SetupDrafts
        with runtime_lease(self.root):
            SetupDrafts(self.state).begin()
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

    def review_setup(self) -> dict[str, Any]:
        with runtime_lease(self.root):
            state = self.state.load()
            if state['play_gate'] != 'setup_draft' or not state.get('draft', {}).get('main_character'):
                raise RuntimeError('Finish the party and choose its main character before review.')
            operation = {'id': 'setup-' + uuid.uuid4().hex, 'kind': 'setup', 'stage': 'prepare_setup', 'before': {'day': 1, 'phase': PHASES[0], 'progress': 0}, 'message': 'Prepare the complete starting party for review.', 'answers': [], 'revision': 0, 'results': {}, 'dice': {}}
            self.state.save({'operation': operation, 'play_gate': 'running'})
            return self._drive()

    def end_day(self) -> dict[str, Any]:
        with runtime_lease(self.root):
            self.require_open_play()
            state = self.state.load()
            self.state.save({'sleep_until_day': state['position']['day'] + 1, 'play_gate': 'sleep_pending'})
            return self._drive()

    def continue_run(self) -> dict[str, Any]:
        with runtime_lease(self.root):
            return self._drive()

    def _context(self, operation: dict[str, Any]) -> dict[str, Any]:
        state = self.state.load()
        return {
            'turn_id': operation['id'], 'campaign_id': (state.get('draft') or {}).get('campaign_id', state.get('campaign_id', 'legacy')),
            'position': operation['before'], 'message': operation['message'],
            'answers': operation['answers'], 'history': state.get('history', []),
            'game_cache': state.get('game_cache', {}), 'revision': operation['revision'],
            'review_proposal': state.get('proposal'), 'completed_day': state.get('completed_day'),
            'world_pool': state.get('world_pool'), 'review_kind': operation.get('review_gate'),
            'saved_rolls': state.get('saved_rolls', {}), 'draft': state.get('draft'),
            'event_to_encounter': operation.get('event_to_encounter'),
        }

    def _checkpoint(self, operation: dict[str, Any], stage: str, **changes: Any) -> None:
        operation['stage'] = stage
        self.state.save({'operation': operation, **changes})

    def _drive(self) -> dict[str, Any]:
        state = self.state.load()
        if not state.get('operation') and state['play_gate'] == 'sleep_pending':
            position = state['position']
            operation = {'id': 'rest-' + uuid.uuid4().hex, 'kind': 'turn', 'sleep': True, 'stage': 'route', 'before': position,
                         'message': f"Rest only until the next phase boundary ({1 - position.get('progress', 0)} phase). Award only earned rest. Respect each NPC's explicit orders and sleep schedule; use AI decisions where no schedule exists. Stop if interrupted. Do not resolve the remainder of the night.",
                         'answers': [], 'revision': 0, 'results': {}, 'dice': {}}
            self.state.save({'operation': operation, 'play_gate': 'running'})
            state = self.state.load()
        if not state.get('operation') or state['play_gate'] in {'awaiting_clarification', 'day_end_review', 'admin_review', 'setup_review'}:
            return self.view()
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
                    proposal = self.modules.prepare_setup(context)
                    self._prepare_review(proposal, operation, 'setup_review')
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
        except Exception:
            # Provider exceptions and traces can contain hidden facts or credentials.
            self.state.save({'play_gate': 'retry', 'message': 'Processing stopped safely. Use /retry to resume this step.'})
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
                    self.state.save({'operation': None, 'play_gate': operation.get('return_gate', 'open'), 'message': response.get('answer', '')})
                elif response.get('status') == 'needs_clarification':
                    self._checkpoint(operation, 'admin', play_gate='awaiting_clarification', pending_clarification={'question': '\n'.join(response.get('questions', []))})
                else:
                    raise RuntimeError('Administrative analysis is incomplete.')
                return
            elif stage == 'resolve':
                lead = self.modules.resolve(results['specialists'], context, operation.get('dice_result'))
                lead['turn_id'] = operation['id']
                resolution = lead.get('resolution_record') or lead
                status = lead.get('status')
                if status == 'needs_clarification':
                    question = lead.get('player_question') or resolution.get('clarification_request') or {'question': 'Please clarify your action.'}
                    self._checkpoint(operation, 'resolve', play_gate='awaiting_clarification', pending_clarification=question)
                    return
                if status == 'awaiting_dice':
                    request = resolution.get('dice_request') or {}
                    self._roll(operation, request)
                    continue
                if status == 'blocked' and lead.get('evidence_expansion_request') and operation.get('expansions', 0) < 2:
                    operation['expansions'] = operation.get('expansions', 0) + 1
                    operation['evidence_note'] = lead['evidence_expansion_request'].get('evidence_note')
                    self._checkpoint(operation, 'evidence')
                    continue
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
                if operation.get('event_to_encounter') and resolution.get('encountered_event_id') != operation['event_to_encounter']['id']:
                    raise RuntimeError('The due world event must be encountered before this action completes.')
                results.update(resolution=lead, after=after, transitions=transitions)
                self._checkpoint(operation, 'narrate')
                self._start_background(operation, context)
            elif stage == 'narrate':
                self._start_background(operation, context)
                results['narration'] = self.modules.narrate(results['resolution'], context)
                self._checkpoint(operation, 'record')
            elif stage == 'record':
                results['record'] = self.modules.record(results['resolution'], context)
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
                self.state.save({
                    'position': after, 'history': history, 'operation': None,
                    'play_gate': gate, 'sleep_until_day': state.get('sleep_until_day') if keep_sleeping else None,
                    'review_after_interrupt': review_due and interrupted,
                    'message': message, 'state_version': state.get('state_version', 0) + 1,
                    'game_cache': results['record'].get('cache_delta') or state.get('game_cache', {}),
                    'pending_dice': None, 'pending_clarification': None,
                    'completed_day': operation['before']['day'] if after['day'] > operation['before']['day'] else state.get('completed_day'),
                    'saved_rolls': {**state.get('saved_rolls', {}), operation['id']: operation['dice']},
                    'pending_world_event': None if operation.get('event_to_encounter') else state.get('pending_world_event'),
                })
                return
            else:
                raise RuntimeError('Unknown saved stage.')
        raise RuntimeError('Continuation limit reached; requires review.')

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
        operation['results'] = {}
        gate = state['play_gate']
        operation['kind'] = 'day_end' if gate == 'day_end_review' else 'setup' if gate == 'setup_review' else 'turn'
        operation['stage'] = 'prepare_day' if gate == 'day_end_review' else 'prepare_setup' if gate == 'setup_review' else 'route'
        if gate == 'admin_review':
            operation['message'] = '{Revise the entire pending proposal, checking rules and dependent outcomes. ' + message + '}'
        self.state.save({'operation': operation, 'play_gate': 'running', 'message': 'Rechecking the revised proposal.'})
        return self._drive()

    def _prepare_review(self, proposal: dict[str, Any], operation: dict[str, Any], gate: str) -> None:
        from brain.game_modules import admin_module
        proposal = {**proposal, 'status': 'proposal_ready', 'proposal_id': operation['id'] + '-v' + str(operation['revision'])}
        bound = admin_module('approval').bind_source_versions(proposal, repo_root=self.root)
        self.state.save({'proposal': bound, 'operation': operation, 'play_gate': gate, 'message': proposal.get('answer', 'Review the complete proposed changes.'), 'pending_clarification': None})

    def approve(self, *, confirm_reset: bool = False) -> dict[str, Any]:
        from brain.game_modules import admin_module
        with runtime_lease(self.root):
            state = self.state.load()
            if state['play_gate'] not in {'admin_review', 'day_end_review', 'setup_review'} or not state.get('proposal'):
                raise RuntimeError('There is no proposal awaiting approval.')
            if state['play_gate'] == 'setup_review' and not confirm_reset:
                raise ValueError('Replacement requires explicit confirmation: /approve-reset.')
            operation = state['operation']
            operation['approved'] = admin_module('approval').approve_proposal(state['proposal'])
            operation['review_gate'] = state['play_gate']
            operation['kind'] = 'apply'
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
        state = self.state.load()
        self.state.save({'proposal': None, 'last_receipt': operation['receipt'],
                         'message': 'Approved changes saved.', 'state_version': state.get('state_version', 0) + 1})
        if operation['review_gate'] == 'setup_review':
            self._activate_setup(operation)
        elif operation['review_gate'] == 'day_end_review':
            operation['kind'] = 'world'
            self._checkpoint(operation, 'world', play_gate='world_event_pending')
            self._world(operation)
        else:
            self.state.save({'operation': None, 'play_gate': operation.get('return_gate', 'open') if operation.get('return_gate') == 'day_end_review' else 'open'})

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
        opening = {'id': 'opening-' + draft['campaign_id'], 'kind': 'turn', 'stage': 'route', 'before': {'day': 1, 'phase': PHASES[0], 'progress': 0},
                   'message': 'Begin the approved new campaign. Design the first scenario from the saved party backgrounds and established world lore. Introduce the situation without deciding the player response. No time elapses for this introduction.',
                   'answers': [], 'revision': 0, 'results': {}, 'dice': {}}
        self.state.save({'campaign_id': draft['campaign_id'], 'main_character': draft['main_character'], 'party': draft['characters'],
                         'draft': None, 'setup_status': 'active', 'position': opening['before'], 'operation': opening,
                         'history': [], 'game_cache': {}, 'saved_rolls': {}, 'pending_world_event': None, 'world_pool': None,
                         'completed_day': None, 'pending_dice': None, 'pending_clarification': None, 'day_end': None, 'play_gate': 'running'})
        self._turn(opening, self._context(opening))

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
            self.state.save({'pending_world_event': None, 'operation': None, 'play_gate': 'open', 'proposal': None,
                             'last_world_check': {'day': state['position']['day'], 'roll': roll, 'trigger': owner},
                             'message': 'Day-end changes saved. The next day is ready.'})
            return
        event = self.modules.world(self._context(operation), roll, pool)
        if event.get('roll') != roll or event.get('selected_trigger') != owner:
            raise ValueError('World event does not match the saved roll and frozen pool.')
        if not event.get('encounter_condition') or event.get('latest_phase') not in PHASES or not event.get('generated_event'):
            raise ValueError('World event is missing its setup, encounter condition, or deadline.')
        event = {**event, 'id': 'event-' + operation['id'], 'day': state['position']['day'], 'status': 'pending'}
        self.state.save({'pending_world_event': event, 'operation': None, 'play_gate': 'open', 'proposal': None,
                         'message': 'Day-end changes saved. The next day is ready.'})

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
    def _time(before: dict[str, Any], lead: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        clock = PhaseClock()
        start = clock.position(before['day'], before['phase'], before.get('progress', 0))
        current = start
        transitions: list[dict[str, Any]] = []
        for change in (lead.get('resolution_record') or lead).get('time_changes', []):
            duration = change.get('phases_elapsed', change.get('phases', change.get('phase_cost')))
            if duration is not None:
                elapsed = float(duration)
                if not math.isfinite(elapsed) or elapsed < 0 or elapsed > 9:
                    raise ValueError('Invalid duration; multi-day actions require separate daily gates.')
                steps = clock.advance(current, elapsed)
                total = current.progress + elapsed
                base = steps[-1].current if steps else current
                after = clock.position(base.day, base.phase, round(total % 1, 8))
            else:
                after = clock.position(change.get('after_day', change.get('day', current.day)), change.get('after_phase', change.get('phase', current.phase)), change.get('after_progress', change.get('progress', current.progress)))
                steps = clock.transitions_from_time_change(current, change)
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
