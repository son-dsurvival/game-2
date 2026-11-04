"""Adapters for the existing game scripts. No terminal IO or approval decisions."""
from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from backend.background_state import BackgroundStateStore
from backend.phase_clock import PhaseClock
from backend.phase_tick import PhaseTickEngine
from brain.build_canon_section_index import build_index as canon_index
from brain.build_evidence_index import build_index as evidence_index
from brain.evidence_bundle import EvidenceBundleBuilder
from brain.dice import DiceJournal
from brain.lead_resolver import LeadResolver
from brain.narrator import Narrator
from brain.persistence import atomic_json
from brain.recorder import SessionRecorder
from brain.specialists.coverage_check import CoverageCheck
from brain.specialists.runner import SpecialistRunner
from brain.turn_router import TurnRouter


# Sibling imports in the existing spaced folder require this one explicit seam.
def admin_module(name: str) -> Any:
    folder = str(Path(__file__).resolve().parents[1] / 'outside game')
    if folder not in sys.path:
        sys.path.insert(0, folder)
    return importlib.import_module(name)


class GameModules:
    def __init__(self, root: Path):
        self.root = root

    def recover(self) -> None:
        admin_module('admin_editor').AdminEditor(self.root).recover()

    def refresh(self) -> None:
        atomic_json(self.root / 'brain/info/evidence_index.json', evidence_index(self.root / 'markdown_files', force=True))
        atomic_json(self.root / 'brain/info/canon_section_index.json', canon_index(self.root))

    def route(self, message: str, context: dict[str, Any]) -> dict[str, Any]:
        return TurnRouter(self.root, require_git=False).route(
            message, campaign_mode=True, current_phase=context['position']['phase'], current_state=context,
        ).to_dict()

    def evidence(self, route: dict[str, Any], context: dict[str, Any], note: str | None = None) -> dict[str, Any]:
        self.refresh()
        message = context['message']
        if context.get('answers'):
            message += '\nPlayer clarifications:\n' + '\n'.join(context['answers'])
        bundle = EvidenceBundleBuilder(self.root).build(
            route, player_input=message, current_state=context,
            conversation_history=context.get('history', []), evidence_note=note,
        ).to_dict()
        return {**route, 'evidence_bundle': bundle}

    def specialists(self, bundle: dict[str, Any], context: dict[str, Any], extra: tuple[str, ...] = ()) -> dict[str, Any]:
        result = SpecialistRunner(self.root).run(bundle, [*bundle.get('required_specialists', []), *extra])
        result['mode'] = bundle.get('mode')
        result['request_type'] = bundle.get('request_type')
        result['coverage_check'] = CoverageCheck().check(result)
        return result

    def resolve(self, analysis: dict[str, Any], context: dict[str, Any], dice: dict[str, Any] | None = None) -> dict[str, Any]:
        return LeadResolver(self.root).resolve(analysis, chat_context=context, campaign_context=context, dice_result=dice)

    def narrate(self, resolution: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return Narrator(rules_path=self.root / 'markdown_files/game rules (1).md').render(resolution)

    def record(self, resolution: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        # Recorder only sees the foreground resolution. Hidden phase results are
        # stored independently and cannot reach this input through shared state.
        return SessionRecorder(self.root).record({**resolution, 'position': context['position']})

    def admin(self, bundle: dict[str, Any], analysis: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        coverage = analysis.get('coverage_check') or CoverageCheck().check(analysis)
        if not coverage.get('ready_for_lead_resolver'):
            raise RuntimeError('Administrative specialists need more evidence.')
        # All runtime admin work supplies the mandatory cache-first analysis;
        # the standalone script's no_specialists switch is never used here.
        result = admin_module('admin_agent').AdminAgent(self.root).respond(bundle, specialist_output=analysis)
        if result.get('changes'):
            memory = self.root / 'markdown_files/TEMP_MEMORY.md'
            pending = SessionRecorder(self.root).pending_records() if memory.exists() else []
            targets = {item.get('target_file') for item in result['changes']}
            if pending and 'markdown_files/TEMP_MEMORY.md' not in targets:
                raise RuntimeError('The edit proposal must also reconcile pending working records.')
        return result

    def prepare_setup(self, context: dict[str, Any]) -> dict[str, Any]:
        required = {'status sheet.md', 'character relationship.md', 'Ledger Resources.md', 'Experimentation Register.md', 'Branch Registry.md', 'TEMP_MEMORY.md', '🌍 CORE WORLD FRAME (REFINED).md'}
        task = (
            'Prepare a NEW CAMPAIGN replacement proposal, not an edit to existing characters. '
            'Use the approved draft inputs below to derive rule-compliant classes, equipment, money, skills, '
            'relationships, all status values, and penalties below 3. Do not rebalance zero stats. '
            'Respect established world lore and rules. Include ALL characters and designate the main character; '
            'others act autonomously unless instructed. Use registered readable templates. '
            'Reset campaign state in EVERY one of these files: ' + ', '.join(sorted(required)) + '. '
            'Preserve all world lore exactly, replacing ONLY Event log and Game log contents with empty starting logs. '
            'Do not change rules, reference terminology, code, or templates. TEMP_MEMORY uses template temp_memory. '
            'For empty existing documents use fill with template values. Present all derived details for review.\n'
            + json.dumps(context['draft'], ensure_ascii=False)
        )
        local = {**context, 'message': '{' + task + '}', 'history': [], 'game_cache': {}}
        route = self.route(local['message'], local)
        route['turn_id'] = context['turn_id']
        bundle = self.evidence(route, local)
        analysis = self.specialists(bundle, local, ('class',))
        proposal = self.admin(bundle, analysis, local)
        if proposal.get('status') != 'proposal_ready':
            raise RuntimeError('Character creation needs clarification or more evidence.')
        changes = proposal['changes']
        targets = {item['target_file'] for item in changes}
        expected = {'markdown_files/' + name for name in required}
        if targets != expected:
            raise RuntimeError('Setup must replace all campaign records without editing rules or templates.')
        world_path = 'markdown_files/🌍 CORE WORLD FRAME (REFINED).md'
        original = (self.root / world_path).read_text(encoding='utf-8')
        updated = original
        for change in changes:
            if change['target_file'] != world_path:
                continue
            old = change.get('old_text', '')
            if not old or updated.count(old) != 1:
                raise RuntimeError('World reset requires exact log edits, not full template recreation.')
            updated = updated.replace(old, change.get('new_text', ''), 1)
        def lore(text: str) -> str:
            return re.sub(r'^## (?:Event log|Game log)\s*\n.*?(?=^## |\Z)', '', text, flags=re.M | re.S)
        if lore(original) != lore(updated):
            raise RuntimeError('New-game setup cannot change world lore.')
        return proposal

    def prepare_day(self, context: dict[str, Any]) -> dict[str, Any]:
        recorder = SessionRecorder(self.root)
        records = recorder.pending_records(day=context['completed_day'])
        task = (
            'Prepare ONE day-end proposal: promote these player-known working records, update the Event log, '
            'and reconcile TEMP_MEMORY. Check all rules and dependent consequences using the saved rolls; do not reroll. '
            'World specialist: return world_pool with explicit number lists covering 1–100 once, based on the current '
            'rules and prior approved pool. Do not generate a next-day event or roll yet. '
            'Do not change rules or lore. Preserve existing facts outside approved revisions.\n'
            + json.dumps({'records': records, 'prior_pool': context.get('world_pool'), 'saved_rolls': context.get('saved_rolls'), 'review': context.get('review_proposal'), 'revisions': context.get('answers')}, ensure_ascii=False)
        )
        local = {**context, 'message': '{' + task + '}'}
        route = self.route(local['message'], local)
        route['turn_id'] = context['turn_id']
        bundle = self.evidence(route, local)
        analysis = self.specialists(bundle, local, ('world',))
        world: dict[str, Any] = next((item for item in analysis.get('specialist_results', []) if item.get('specialist') == 'world'), {})
        pool = world.get('world_pool')
        proposal = self.admin(bundle, analysis, local)
        if proposal.get('status') != 'proposal_ready':
            raise RuntimeError('Day-end proposal needs more review.')
        # Export exact player-visible exchanges, never private model requests.
        exchanges = [item for item in context.get('history', []) if item.get('day') == context['completed_day']]
        lines = [f"### Day {context['completed_day']} — approved prompt/result history"]
        for exchange in exchanges:
            lines.extend([f"#### {exchange['turn_id']}", 'Prompt:', *['    ' + line.replace('```', '` ` `') for line in exchange['prompt'].splitlines()], 'Result:', *['    ' + line.replace('```', '` ` `') for line in exchange['result'].splitlines()], ''])
        target = 'markdown_files/🌍 CORE WORLD FRAME (REFINED).md'
        original = (self.root / target).read_text(encoding='utf-8')
        updated = original
        other = []
        for change in proposal['changes']:
            if change['target_file'] != target:
                other.append(change)
                continue
            old = change.get('old_text', '')
            if not old or updated.count(old) != 1:
                raise RuntimeError('World log proposal cannot be composed safely.')
            updated = updated.replace(old, change.get('new_text', ''), 1)
        if '## Game log' not in updated:
            raise RuntimeError('World frame requires a Game log heading.')
        updated = updated.replace('## Game log', '## Game log\n\n' + '\n'.join(lines), 1)
        other.append({'target_file': target, 'action': 'update', 'old_text': original, 'new_text': updated, 'reason': 'Combined reviewed event and visible prompt/result log.'})
        proposal = {key: value for key, value in proposal.items() if key not in {'proposal_digest', 'expected_source_hashes', 'approval'}}
        proposal['changes'] = other
        return {'proposal': proposal, 'world_pool': pool, 'turn_ids': [item['turn_id'] for item in records]}

    def world(self, context: dict[str, Any], roll: int, pool: dict[str, Any]) -> dict[str, Any]:
        local = {**context, 'message': 'World specialist: design the next-day event from this FROZEN approved pool and saved roll. Do not alter the pool or resolve outcomes. Return world_event with roll, selected_trigger, generated_event, encounter_condition and latest_phase.\n' + json.dumps({'roll': roll, 'pool': pool, 'day': context['position']['day']})}
        route = self.route(local['message'], local)
        route['turn_id'] = context['turn_id'] + '-world'
        bundle = self.evidence(route, local)
        analysis = self.specialists(bundle, local, ('world',))
        if not analysis['coverage_check'].get('ready_for_lead_resolver'):
            raise RuntimeError('World preparation needs more evidence.')
        world = next(item for item in analysis['specialist_results'] if item['specialist'] == 'world')
        if world.get('status') != 'complete' or not isinstance(world.get('world_event'), dict):
            raise RuntimeError('World event is not complete.')
        return world['world_event']

    def reconcile(self, operation: dict[str, Any], context: dict[str, Any]) -> None:
        if operation.get('review_gate') == 'day_end_review':
            SessionRecorder(self.root).mark_promoted(operation.get('turn_ids', []))

    def background(self, transitions: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        store = BackgroundStateStore(
            self.root / 'brain/state/background_visible.md',
            private_state_path=self.root / 'brain/state/background_state.json',
        )
        clock = PhaseClock()
        for transition in transitions:
            existing = next((tick for tick in store.load_ticks() if tick['tick_id'] == transition['tick_id']), None)
            if existing:
                if existing.get('interrupt'):
                    return {'status': 'interrupted', 'interrupt': existing['interrupt']}
                continue
            previous_ticks = store.load_ticks()
            if previous_ticks and isinstance(previous_ticks[-1].get('next_context'), dict):
                context = {**context, **previous_ticks[-1]['next_context']}
            before = transition['previous']
            position = clock.position(before['day'], before['phase'], before.get('progress', 0))

            def resolve_tick(plan: dict[str, Any]) -> dict[str, Any]:
                hidden = {**context, 'turn_id': plan['tick_id'], 'position': plan['position'],
                          'message': 'Resolve this hidden phase without revealing it to the player: ' + json.dumps(plan),
                          'history': [], 'answers': [], 'private_background': store.load_ticks()}
                route = self.route(hidden['message'], hidden)
                route['turn_id'] = plan['tick_id']
                evidence = self.evidence(route, hidden)
                analysis = self.specialists(evidence, hidden)
                lead = self.resolve(analysis, hidden)
                if lead.get('status') == 'awaiting_dice':
                    request = lead['resolution_record']['dice_request']
                    identity = context['campaign_id'] + '/' + plan['tick_id'] + '/' + str(request.get('roll_id', 'action'))
                    dice = DiceJournal(self.root).roll(identity, sides=request.get('sides', 20), count=request.get('count', 1))
                    lead = self.resolve(analysis, hidden, dice)
                if lead.get('status') != 'resolved':
                    return {'status': 'blocked'}
                resolution = lead['resolution_record']
                packet = resolution.get('background_packet') or {}
                return {**resolution, **packet, 'status': 'resolved', 'actions': packet.get('actions', plan['actions']),
                        'world_updates': [{'description': resolution.get('outcome'), 'visibility': 'hidden'}]}

            result = PhaseTickEngine(store).run(position, 1 - position.progress, context=context, resolve_tick=resolve_tick)
            if result['status'] != 'complete':
                return result
        return {'status': 'complete'}
