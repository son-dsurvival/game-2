"""Adapters for the existing game scripts. No terminal IO or approval decisions."""
from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from backend.background_state import BackgroundStateStore
from backend.phase_clock import PHASES, PhaseClock
from backend.phase_tick import PhaseTickEngine
from brain.build_canon_section_index import build_index as canon_index
from brain.build_evidence_index import build_index as evidence_index
from brain.branch_discovery import BranchDiscovery
from brain.evidence_bundle import EvidenceBundleBuilder
from brain.dice import DiceJournal
from brain.lead_resolver import LeadResolver
from brain.model_gateway import ModelGateway
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
        event = context.get('event_to_encounter')
        chat = context
        if isinstance(event, dict):
            chat = {
                **context,
                'pending_world_event': event,
                'message': str(context.get('message', '')) + '\n\nA scheduled world event is DUE NOW and must be staged and resolved this turn; do not let the declared action bypass it.\n' + json.dumps({key: event.get(key) for key in ('id', 'generated_event', 'encounter_condition', 'latest_phase', 'selected_trigger')}, ensure_ascii=False),
            }
        return LeadResolver(self.root).resolve(analysis, chat_context=chat, campaign_context=chat, dice_result=dice)

    def narrate(self, resolution: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return Narrator(rules_path=self.root / 'markdown_files/game rules (1).md').render(resolution)

    def record(self, resolution: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        # Record the resolved AFTER position, not the turn's start, so two rest
        # turns do not both claim the same boundary and read as duplicates.
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

    def _inject_world_rules(self, bundle_record: dict[str, Any]) -> dict[str, Any]:
        """Deterministically include the Dynamic World Event Engine rules so the
        world specialist never blocks on missing evidence for pool/event work."""
        index_path = self.root / 'brain/info/evidence_index.json'
        try:
            index = json.loads(index_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return bundle_record
        wanted: list[dict[str, Any]] = []
        keywords = (
            'world event', 'event trigger', 'number pool', 'event roll', 'event tier',
            'event check', 'nothing result', 'events outside', 'tracking and transparency',
            'changing the pool', 'adjustment size', 'number transfer', 'event check timing',
            'generating the specific event', 'core purpose',
        )
        for root in index.get('under', []):
            if not isinstance(root, dict):
                continue
            source = root.get('location')
            if not isinstance(source, str):
                continue
            def walk(node: dict[str, Any], path: list[str]) -> None:
                location = node.get('location', '')
                name = str(node.get('name', ''))
                full = (name + ' ' + ' '.join(path)).lower()
                if str(location).startswith('lines ') and any(key in full for key in keywords):
                    wanted.append({
                        'id': f"world-rule-{source}-{location}",
                        'name': name, 'source': source, 'location': location,
                        'path': [*path, name], 'description': str(node.get('description', '')),
                    })
                for child in node.get('under', []):
                    if isinstance(child, dict):
                        walk(child, [*path, name])
            walk(root, [str(root.get('name', ''))])
        bundle = bundle_record.get('evidence_bundle', bundle_record)
        sections = bundle.get('selected_sections')
        if not isinstance(sections, list):
            sections = []
            bundle['selected_sections'] = sections
        existing = {str(s.get('id')) for s in sections}
        for section in wanted:
            if section['id'] not in existing:
                sections.append(section)
                existing.add(section['id'])
        scoped = bundle.setdefault('specialist_bundles', {}).setdefault('world', {})
        world_sections = scoped.get('selected_sections')
        if not isinstance(world_sections, list):
            world_sections = []
            scoped['selected_sections'] = world_sections
        world_ids = {str(s.get('id')) for s in world_sections}
        for section in wanted:
            if section['id'] not in world_ids:
                world_sections.append(section)
                world_ids.add(section['id'])
        return bundle_record

    @staticmethod
    def _default_world_pool() -> dict[str, list[int]]:
        return {
            'Monsters': [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45, 49, 53, 57, 61, 65, 69, 73, 77],
            'Business': [2, 6, 10, 14, 18, 22, 26, 30, 34, 38, 42, 46, 50, 54, 58, 62, 66, 70, 74, 78],
            'People': [3, 7, 11, 15, 19, 23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63, 67, 71, 75, 79, 81, 85, 89, 93, 97],
            'Weather': [4, 8, 12, 16, 20, 24, 28, 32, 36, 40],
            'Nothing': [44, 48, 52, 56, 60, 64, 68, 72, 76, 80, 82, 83, 84, 86, 87, 88, 90, 91, 92, 94, 95, 96, 98, 99, 100],
        }

    def prepare_character_addition(self, context: dict[str, Any]) -> dict[str, Any]:
        draft = context.get('draft') or {}
        mode = draft.get('mode')
        character = (draft.get('characters') or [{}])[0]
        main = context.get('main_character')
        existing_party = context.get('party') or []

        def read(name: str) -> str:
            try:
                return (self.root / 'markdown_files' / name).read_text(encoding='utf-8')
            except OSError:
                return ''

        status = read('status sheet.md')
        ledger = read('Ledger Resources.md')
        relationships = read('character relationship.md')
        task = (
            'Add ONE new ' + ('player character' if mode == 'new_character' else 'NPC party member') +
            ' to the ACTIVE campaign. The existing main character is ' + str(main) + ' and must NOT change; '
            'an NPC party member is not the main character. Do NOT reset or replace existing content: only append. '
            'Derive rule-compliant class, equipment, money, skills, relationships and derived stats from the rules '
            'and the character draft. Use APPEND-STYLE exact edits: each old_text MUST be quoted exactly from the '
            'CURRENT file content shown below, and new_text must keep it and append the new character. '
            'If a starting class package is not defined, derive a defensible one from the rules and the description. '
            'Only target status sheet.md, Ledger Resources.md, and character relationship.md.\n'
            'CURRENT status sheet:\n<<<STATUS\n' + status + '\nSTATUS>>>\n'
            'CURRENT ledger:\n<<<LEDGER\n' + ledger + '\nLEDGER>>>\n'
            'CURRENT relationships:\n<<<REL\n' + relationships + '\nREL>>>\n'
            'NEW CHARACTER:\n' + json.dumps({k: character.get(k) for k in ('identity', 'stats', 'description', 'class')}, ensure_ascii=False)
        )
        local = {**context, 'message': '{' + task + '}'}
        route = self.route(local['message'], local)
        route['turn_id'] = context['turn_id']
        bundle = self.evidence(route, local)
        analysis = self.specialists(bundle, local, ('character',))
        proposal = self.admin(bundle, analysis, local)
        if proposal.get('status') != 'proposal_ready':
            return {'status': 'needs_clarification', 'questions': proposal.get('questions') or [], 'answer': proposal.get('answer', ''),
                    'conflicts': proposal.get('conflicts') or []}
        allowed = {'markdown_files/status sheet.md', 'markdown_files/Ledger Resources.md', 'markdown_files/character relationship.md', 'markdown_files/TEMP_MEMORY.md'}
        targets = {c.get('target_file') for c in proposal.get('changes', []) if isinstance(c, dict)}
        if not targets or not targets <= allowed:
            raise RuntimeError('Character addition may only edit character records, not reset campaign files.')
        return proposal

    def prepare_specialist_install(self, context: dict[str, Any], proposal_data: dict[str, Any]) -> dict[str, Any]:
        from brain.specialists.registry import validate_created_definition
        definition = validate_created_definition(proposal_data)
        if definition is None:
            raise ValueError('Specialist proposal is invalid or duplicates an existing specialist.')
        path = self.root / 'markdown_files/Branch Registry.md'
        original = path.read_text(encoding='utf-8')
        title = definition.name.replace('_', ' ').title()
        if re.search(rf'^##\s+{re.escape(title)}\s*$', original, re.M | re.I):
            raise ValueError('Branch already exists in the registry.')
        section = '\n'.join([
            f'## {title}',
            'status: unlocked',
            f'specialist: {definition.name}',
            'template: none',
            'activation tags: ' + (', '.join(definition.activation_tags) or 'none'),
            f'reason: approved Create Specialist proposal ({definition.purpose[:180]})',
        ])
        unlock_rules = re.search(r'^##\s+Unlock Rules\s*$', original, re.M)
        if unlock_rules:
            updated = original[:unlock_rules.start()] + section + '\n\n' + original[unlock_rules.start():]
        else:
            updated = original.rstrip() + '\n\n' + section + '\n'
        change = {'target_file': 'markdown_files/Branch Registry.md', 'action': 'update', 'old_text': original, 'new_text': updated, 'reason': 'Install approved Create Specialist proposal.'}
        return {'status': 'proposal_ready', 'answer': f'Install specialist {definition.name}?', 'changes': [change], 'evidence': [], 'instructions': [], 'questions': [], 'conflicts': [], 'approval_required': True}

    def setup_chat(self, draft: dict[str, Any], player_message: str) -> dict[str, Any]:
        """Use the model as a conversational collector, not as the validator."""
        partial_value = draft.get('partial')
        partial: dict[str, Any] = partial_value if isinstance(partial_value, dict) else {}
        history_value = draft.get('conversation')
        history: list[Any] = history_value if isinstance(history_value, list) else []
        prompt = (
            'You are a warm, concise tabletop game-master assistant collecting ONE character for campaign setup. '
            'Have a natural conversation instead of presenting a form. Extract only information the player stated or clearly accepted. '
            'Ask for whatever is still missing, but do not ask for fields already known. A complete character requires identity '
            '(name, age, race/ancestry), six starting stats named AGI, INT, STR, END, WIS, PRE totaling exactly 30, a description, '
            'and a class concept. If the player asks you to create or suggest a class, you may provide one. Do not write files, '
            'change rules, or invent unstated personal facts. Return JSON only with this shape:\n'
            '{"assistant_message":"...", "complete":false, "party_done":false, "main_character":null, "draft":{"identity":{},"stats":{},"description":"","class":""}}\n'
            'The draft object is a PATCH: omit fields not newly known. Set complete true only when every required field is present '
            'and the stats total 30. If stats are missing or invalid, ask naturally for them. If the player explicitly names '
            'the main character or says the party is ready/done, set main_character and/or party_done. Never set those fields '
            'based only on a guess.\n'
            + json.dumps({'mode': draft.get('mode'), 'main_character': draft.get('main_character'),
                          'existing_characters': draft.get('characters', []), 'known': partial,
                          'history': history[-8:], 'player_message': player_message}, ensure_ascii=False)
        )
        try:
            result = ModelGateway(self.root).complete(
                stage='setup.chat',
                messages=[{'role': 'system', 'content': prompt}],
                json_mode=True,
                temperature=0.2,
                max_retries=1,
            )
            parsed = json.loads(result.content)
            if not isinstance(parsed, dict):
                raise ValueError('Setup chatbot returned a non-object response.')
            parsed['user_message'] = player_message
            return parsed
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
            # The deterministic collector remains available if the provider is down.
            return {'status': 'fallback'}

    def _attach_setup_sources(self, bundle: dict[str, Any], filenames: set[str]) -> None:
        """Give setup's Admin Agent exact private sources; never ask the player for them."""
        evidence = bundle.get('evidence_bundle')
        if not isinstance(evidence, dict):
            return
        sources = evidence.setdefault('admin_sources', [])
        if not isinstance(sources, list):
            sources = []
            evidence['admin_sources'] = sources
        template_names = {
            'status sheet.md': 'character_status',
            'character relationship.md': 'character_relationship',
            'Ledger Resources.md': 'ledger_resources',
            'Experimentation Register.md': 'experimentation_register',
            'Branch Registry.md': 'branch_registry',
            '🌍 CORE WORLD FRAME (REFINED).md': 'core_world_frame',
        }
        source_paths: list[tuple[str, Path]] = []
        for filename in sorted(filenames):
            campaign_path = self.root / 'markdown_files' / filename
            if campaign_path.is_file():
                source_paths.append((f'markdown_files/{filename}', campaign_path))
            template_name = template_names.get(filename)
            if template_name:
                template_path = self.root / 'outside game' / 'templates' / f'{template_name}.md'
                if template_path.is_file():
                    source_paths.append((f'outside game/templates/{template_name}.md', template_path))
        known = {str(item.get('source')) for item in sources if isinstance(item, dict)}
        for relative, path in source_paths:
            if relative in known:
                continue
            try:
                content = path.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                continue
            sources.append({'source': relative, 'kind': 'setup_exact_source', 'content': content})

    def prepare_setup(self, context: dict[str, Any]) -> dict[str, Any]:
        required = {'status sheet.md', 'character relationship.md', 'Ledger Resources.md', 'Experimentation Register.md', 'Branch Registry.md', 'TEMP_MEMORY.md', '🌍 CORE WORLD FRAME (REFINED).md'}
        task = (
            'Prepare a NEW CAMPAIGN replacement proposal, not an edit to existing characters. '
            'The private admin_sources include the exact current campaign files and registered templates; use them directly. '
            'Never ask the player to provide file contents, template names, backend details, or derivation formulas. '
            'Known rule derivations are: HP = END * 5; MP = WIS * 5; Stamina = STR + END; Initiative = AGI + INT; '
            'Carry Load = STR * 10; Physical resistance = END; Magical resistance = INT + WIS; Mental resistance = WIS; '
            'Social resistance = PRE. If a status template labels Stamina as SP, record that mapping as a transparent setup '
            'assumption for approval. Defense is domain-specific and must use the relevant action/reaction rules, not an invented '
            'universal formula. There is no universal starting formula for money, equipment, skills, or relationship tiers: '
            'derive them transparently from the character background and class concept, label assumptions, and include them in '
            'the approval proposal instead of asking the player to define rules. '
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
        bundle = self._inject_world_rules(bundle)
        self._attach_setup_sources(bundle, required)
        analysis = self.specialists(bundle, local, ('class', 'world'))
        world: dict[str, Any] = next((item for item in analysis.get('specialist_results', []) if item.get('specialist') == 'world'), {})
        pool = world.get('world_pool') if isinstance(world.get('world_pool'), dict) else None
        if not pool:
            pool = self._default_world_pool()
        proposal = self.admin(bundle, analysis, local)
        if proposal.get('status') != 'proposal_ready':
            return {'status': 'needs_clarification', 'questions': proposal.get('questions') or [], 'answer': proposal.get('answer', ''),
                    'conflicts': proposal.get('conflicts') or []}
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
        return {'proposal': proposal, 'world_pool': pool}

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
        bundle = self._inject_world_rules(bundle)
        analysis = self.specialists(bundle, local, ('world',))
        world: dict[str, Any] = next((item for item in analysis.get('specialist_results', []) if item.get('specialist') == 'world'), {})
        pool = world.get('world_pool')
        if not isinstance(pool, dict) or not pool:
            pool = context.get('world_pool') or self._default_world_pool()
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
        tier = 'unknown'
        try:
            status_text = (self.root / 'markdown_files/status sheet.md').read_text(encoding='utf-8')
            match = re.search(r'^Tier:\s*(.+)$', status_text, re.M)
            if match:
                tier = match.group(1).strip()
        except OSError:
            pass
        local = {**context, 'message': 'World specialist: design the next-day event from this FROZEN approved pool and saved roll. Do not alter the pool or resolve outcomes. Return world_event with roll, selected_trigger, generated_event, encounter_condition and latest_phase (one of the nine exact phase labels).\n' + json.dumps({'roll': roll, 'pool': pool, 'day': context['position']['day'], 'player_tier': tier})}
        route = self.route(local['message'], local)
        route['turn_id'] = context['turn_id'] + '-world'
        bundle = self.evidence(route, local)
        bundle = self._inject_world_rules(bundle)
        analysis = self.specialists(bundle, local, ('world',))
        world = next((item for item in analysis.get('specialist_results', []) if isinstance(item, dict) and item.get('specialist') == 'world'), None)
        event = world.get('world_event') if isinstance(world, dict) else None
        if not isinstance(event, dict):
            raise RuntimeError('World event is not complete.')
        phase = next((p for p in PHASES if p.casefold() in str(event.get('latest_phase', '')).casefold()), None)
        if phase:
            event['latest_phase'] = phase
        has_event = event.get('roll') is not None and event.get('selected_trigger') and event.get('generated_event') and event.get('encounter_condition') and event.get('latest_phase')
        if not has_event:
            raise RuntimeError('World event is missing required fields.')
        return event

    def discover_branches(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run the cross-source branch detector at a durable day boundary."""
        data = {
            "player_input": context.get("message", ""),
            "conversation_history": context.get("history", []),
            "game_cache": context.get("game_cache", {}),
            "resolved_turns": context.get("completed_day"),
            "day_end_records": context.get("completed_day"),
        }
        return BranchDiscovery(self.root).discover(data)

    def reconcile(self, operation: dict[str, Any], context: dict[str, Any]) -> None:
        if operation.get('review_gate') == 'day_end_review':
            SessionRecorder(self.root).mark_promoted(operation.get('turn_ids', []))

    @staticmethod
    def _party_directives(context: dict[str, Any]) -> list[dict[str, Any]]:
        """Directives so non-main party members act autonomously in the backend.

        The main character is driven by the player; the others pursue their own
        goals unless the player has given them explicit instructions (which are
        already stored as directives and take priority).
        """
        party_raw = context.get('party')
        party = party_raw if isinstance(party_raw, list) else []
        main = context.get('main_character')
        directives: list[dict[str, Any]] = []
        for member in party:
            identity = member.get('identity') if isinstance(member, dict) else None
            name = identity.get('name') if isinstance(identity, dict) else None
            if not name or str(name) == str(main):
                continue
            slug = re.sub(r'[^a-z0-9]+', '-', str(name).casefold()).strip('-')
            directives.append({
                'directive_id': f'party-{slug}',
                'actor': str(name),
                'task': 'Act autonomously toward your own goals as a party member; never take actions reserved for the main character.',
                'status': 'active',
                'metadata': {
                    'visibility': 'hidden',
                    'ooc_visibility': 'private',
                    'requires_resolution': True,
                    'party_member': True,
                },
            })
        return directives

    def background(self, transitions: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        store = BackgroundStateStore(
            self.root / 'brain/state/background_visible.md',
            private_state_path=self.root / 'brain/state/background_state.json',
        )
        # Non-main party members act autonomously unless explicitly instructed.
        existing_ids = {directive.directive_id for directive in store.load_directives()}
        for directive in self._party_directives(context):
            if directive['directive_id'] not in existing_ids:
                store.upsert_directive(directive)
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
