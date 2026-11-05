import tempfile
import unittest
import threading
from pathlib import Path

from brain.runtime_state import RuntimeStateStore
from pipeline import CampaignPipeline


class ScriptedGame:
    """Offline adapter at the game-module seam; no providers or live campaign."""
    def route(self, message, context):
        return {'request_type': 'admin' if message.startswith('{') else 'in_game', 'required_specialists': [], 'preflight': {'errors': []}}

    def evidence(self, route, context, note=None):
        return {'turn_id': route['turn_id'], 'current_state': context}

    def specialists(self, bundle, context, extra=()):
        return {'turn_id': bundle['turn_id'], 'specialist_results': [], 'coverage_check': {'ready_for_lead_resolver': True}}

    def resolve(self, analysis, context, dice=None):
        return {'status': 'resolved', 'resolution_record': {'status': 'resolved', 'outcome': 'You wait.', 'time_changes': [{'phases_elapsed': 0.5}]}}

    def narrate(self, resolution, context):
        return {'narration': 'The market stirs around you.'}

    def record(self, resolution, context):
        return {'status': 'recorded', 'turn_id': context['turn_id']}

    def background(self, transitions, context):
        return {'status': 'complete'}

    def prepare_day(self, context):
        return {'proposal': self.admin({}, {}, context), 'world_pool': {'People': list(range(1, 101))}, 'turn_ids': []}

    def prepare_setup(self, context):
        if not context.get('answers'):
            return {'status': 'needs_clarification', 'questions': ['Which region is the party from?']}
        return {'proposal': {'status': 'proposal_ready', 'answer': 'Start the campaign?',
                             'changes': [{'target_file': 'markdown_files/TEMP_MEMORY.md', 'action': 'update', 'old_text': 'before', 'new_text': 'started'}]},
                'world_pool': {'People': list(range(1, 101))}}

    def prepare_character_addition(self, context):
        return {'status': 'proposal_ready', 'answer': 'Add the character?',
                'changes': [{'target_file': 'markdown_files/TEMP_MEMORY.md', 'action': 'update', 'old_text': 'before', 'new_text': 'after'}]}

    def prepare_specialist_install(self, context, proposal):
        return {'status': 'proposal_ready', 'answer': 'Install?',
                'changes': [{'target_file': 'markdown_files/TEMP_MEMORY.md', 'action': 'update', 'old_text': 'before', 'new_text': 'installed'}]}

    def world(self, context, roll, pool):
        return {'roll': roll, 'selected_trigger': 'People', 'encounter_condition': 'enter the market', 'latest_phase': 'Evening', 'generated_event': 'A visitor asks for help.'}

    def admin(self, bundle, analysis, context):
        return {'status': 'proposal_ready', 'answer': 'Correct the notes?', 'changes': [{'target_file': 'markdown_files/notes.md', 'action': 'update', 'old_text': 'before', 'new_text': 'after'}]}


class PipelineTests(unittest.TestCase):
    def test_resolved_turn_survives_restart_without_repeating_effects(self):
        with tempfile.TemporaryDirectory() as root:
            RuntimeStateStore(root).save({'play_gate': 'open', 'campaign_id': 'test', 'setup_status': 'active'})
            pipeline = CampaignPipeline(root, modules=ScriptedGame())
            result = pipeline.submit('Wait at the market.')
            self.assertEqual(result['message'], 'The market stirs around you.')
            self.assertEqual(result['position']['progress'], 0.5)
            restarted = CampaignPipeline(root, modules=ScriptedGame())
            self.assertEqual(restarted.resume()['position']['progress'], 0.5)
            self.assertEqual(restarted.resume()['message'], 'The market stirs around you.')

    def test_admin_edit_waits_for_approval_and_does_not_advance_time(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'markdown_files/notes.md'
            target.parent.mkdir()
            target.write_text('before', encoding='utf-8')
            RuntimeStateStore(root).save({'play_gate': 'open', 'campaign_id': 'test'})
            pipeline = CampaignPipeline(root, modules=ScriptedGame())
            review = pipeline.submit('{correct my notes}')
            self.assertEqual(review['status'], 'admin_review')
            self.assertEqual(review['proposal_preview'][0]['target_file'], 'markdown_files/notes.md')
            self.assertEqual(review['proposal_preview'][0]['content'], 'after')
            self.assertEqual(target.read_text(encoding='utf-8'), 'before')
            applied = pipeline.approve()
            self.assertEqual(applied['status'], 'open')
            self.assertEqual(target.read_text(encoding='utf-8'), 'after')
            self.assertEqual(applied['position']['phase'], 'Early Morning')

    def test_day_end_requires_application_then_schedules_a_private_event(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'markdown_files/notes.md'
            target.parent.mkdir()
            target.write_text('before', encoding='utf-8')
            RuntimeStateStore(root).save({'play_gate': 'day_end_pending', 'campaign_id': 'test', 'completed_day': 1, 'position': {'day': 2, 'phase': 'Early Morning', 'progress': 0}})
            pipeline = CampaignPipeline(root, modules=ScriptedGame())
            review = pipeline.prepare_day_end()
            self.assertEqual(review['status'], 'day_end_review')
            # Input at a review gate is a revision, never a new gameplay turn.
            self.assertEqual(pipeline.submit('Walk away')['status'], 'day_end_review')
            self.assertEqual(target.read_text(encoding='utf-8'), 'before')
            applied = pipeline.approve()
            self.assertEqual(applied['status'], 'open')
            self.assertNotIn('visitor', str(applied))
            self.assertNotIn('visitor', str(pipeline.resume()))
            self.assertEqual(target.read_text(encoding='utf-8'), 'after')

    def test_cancelled_multi_character_setup_preserves_active_campaign(self):
        with tempfile.TemporaryDirectory() as root:
            store = RuntimeStateStore(root)
            store.save({'play_gate': 'open', 'campaign_id': 'old', 'position': {'day': 4, 'phase': 'Night', 'progress': 0.5}})
            pipeline = CampaignPipeline(root, modules=ScriptedGame())
            pipeline.begin_setup()
            for name in ('Mira', 'Sol'):
                pipeline.add_character({'name': name, 'age': 24, 'race': 'human'}, {'AGI': 0, 'INT': 30, 'STR': 0, 'END': 0, 'WIS': 0, 'PRE': 0}, 'Curious traveler.', 'AI-created mage')
            draft = pipeline.select_main('Mira')
            self.assertEqual(len(draft['draft']['characters']), 2)
            resumed = CampaignPipeline(root, modules=ScriptedGame())
            self.assertEqual(resumed.resume()['draft']['main_character'], 'Mira')
            restored = resumed.cancel_setup()
            self.assertEqual(restored['position']['day'], 4)
            self.assertEqual(restored['status'], 'open')

    def test_background_overlaps_narration_and_pending_work_blocks_next_action(self):
        started = threading.Event()
        release = threading.Event()

        class ParallelGame(ScriptedGame):
            def resolve(self, analysis, context, dice=None):
                lead = super().resolve(analysis, context, dice)
                lead['resolution_record']['time_changes'] = [{'phases_elapsed': 1}]
                return lead

            def background(self, transitions, context):
                started.set()
                if not release.wait(3):
                    raise RuntimeError('Narration never overlapped background work.')
                return {'status': 'complete'}

            def narrate(self, resolution, context):
                if not started.wait(1):
                    raise RuntimeError('Background was not started before narration.')
                release.set()
                return super().narrate(resolution, context)

        with tempfile.TemporaryDirectory() as root:
            RuntimeStateStore(root).save({'play_gate': 'open', 'campaign_id': 'test'})
            pipeline = CampaignPipeline(root, modules=ParallelGame())
            result = pipeline.submit('Wait a phase')
            self.assertEqual(result['message'], 'The market stirs around you.')
            self.assertEqual(result['position']['phase'], 'Morning')

    def test_clarification_and_provider_failure_resume_with_saved_dice(self):
        class QuestionGame(ScriptedGame):
            failed = False
            def resolve(self, analysis, context, dice=None):
                if not context['answers']:
                    return {'status': 'needs_clarification', 'player_question': {'question': 'Which gate?'}}
                if dice is None:
                    return {'status': 'awaiting_dice', 'resolution_record': {'dice_request': {'sides': 20, 'roll_id': 'gate'}}}
                if not self.failed:
                    self.failed = True
                    raise OSError('provider unavailable')
                result = super().resolve(analysis, context, dice)
                result['resolution_record']['outcome'] = str(dice['result'])
                return result
        with tempfile.TemporaryDirectory() as root:
            RuntimeStateStore(root).save({'play_gate': 'open', 'campaign_id': 'test'})
            game = QuestionGame()
            pipeline = CampaignPipeline(root, modules=game)
            self.assertEqual(pipeline.submit('Enter the gate')['question']['question'], 'Which gate?')
            self.assertEqual(pipeline.submit('The north gate')['status'], 'retry')
            restarted = CampaignPipeline(root, modules=game)
            self.assertEqual(restarted.continue_run()['status'], 'open')

    def test_pending_event_cannot_be_skipped_by_crossing_its_deadline(self):
        class EventGame(ScriptedGame):
            def resolve(self, analysis, context, dice=None):
                result = super().resolve(analysis, context, dice)
                result['resolution_record']['time_changes'] = [{'phases_elapsed': 1}]
                if context.get('event_to_encounter'):
                    result['resolution_record']['encountered_event_id'] = context['event_to_encounter']['id']
                return result
            def narrate(self, resolution, context):
                event_id = resolution['resolution_record'].get('encountered_event_id')
                return {'narration': 'The visitor reaches you.' if event_id else 'Nothing happens.'}
        with tempfile.TemporaryDirectory() as root:
            RuntimeStateStore(root).save({'play_gate': 'open', 'campaign_id': 'test', 'pending_world_event': {'id': 'visitor', 'day': 1, 'latest_phase': 'Morning', 'encounter_condition': 'market entry', 'generated_event': 'A visitor seeks help.'}})
            pipeline = CampaignPipeline(root, modules=EventGame())
            result = pipeline.submit('Wait a phase')
            self.assertEqual(result['message'], 'The visitor reaches you.')
            self.assertEqual(result['status'], 'open')
            self.assertNotIn('generated_event', str(pipeline.resume()))

    def test_sleep_interrupt_stops_at_first_completed_phase(self):
        class InterruptedGame(ScriptedGame):
            def resolve(self, analysis, context, dice=None):
                lead = super().resolve(analysis, context, dice)
                lead['resolution_record']['time_changes'] = [{'phases_elapsed': 1}]
                return lead
            def background(self, transitions, context):
                return {'status': 'interrupted', 'interrupt': {'visibility': 'visible', 'message': 'A knock wakes you.'}}
        with tempfile.TemporaryDirectory() as root:
            RuntimeStateStore(root).save({'play_gate': 'open', 'campaign_id': 'test'})
            pipeline = CampaignPipeline(root, modules=InterruptedGame())
            result = pipeline.end_day()
            self.assertEqual(result['status'], 'open')
            self.assertEqual(result['position']['phase'], 'Morning')
            self.assertIn('A knock wakes you.', result['message'])

    def _seed_open_campaign(self, root):
        target = Path(root) / 'markdown_files/TEMP_MEMORY.md'
        target.parent.mkdir(parents=True)
        target.write_text('before', encoding='utf-8')
        RuntimeStateStore(root).save({
            'play_gate': 'open', 'campaign_id': 'campaign-one',
            'main_character': 'Kael',
            'party': [{'identity': {'name': 'Kael'}, 'stats': {}, 'description': '', 'class': ''}],
            'position': {'day': 1, 'phase': 'Early Morning', 'progress': 0.0},
        })

    def test_new_character_is_added_to_party_after_approval(self):
        with tempfile.TemporaryDirectory() as root:
            self._seed_open_campaign(root)
            pipeline = CampaignPipeline(root, modules=ScriptedGame())
            pipeline.new_character()
            pipeline.add_character({'name': 'Mira', 'age': 22, 'race': 'Human'},
                                   {'AGI': 5, 'INT': 5, 'STR': 5, 'END': 5, 'WIS': 5, 'PRE': 5},
                                   'A scholar.', 'Mage')
            pipeline.select_main('Mira')
            review = pipeline.review_setup()
            self.assertEqual(review['status'], 'character_review')
            self.assertEqual(Path(root, 'markdown_files/TEMP_MEMORY.md').read_text(encoding='utf-8'), 'before')
            result = pipeline.approve()
            self.assertEqual(result['status'], 'open')
            state = RuntimeStateStore(root).load()
            self.assertEqual([m['identity']['name'] for m in state['party']], ['Kael', 'Mira'])
            self.assertEqual(state['main_character'], 'Kael')

    def test_new_party_member_keeps_main_character(self):
        with tempfile.TemporaryDirectory() as root:
            self._seed_open_campaign(root)
            pipeline = CampaignPipeline(root, modules=ScriptedGame())
            pipeline.new_party_member()
            pipeline.add_character({'name': 'Renn', 'age': 31, 'race': 'Human'},
                                   {'AGI': 6, 'INT': 6, 'STR': 6, 'END': 6, 'WIS': 3, 'PRE': 3},
                                   'A road-worn scout.', 'Scout')
            self.assertEqual(pipeline.select_main('Renn')['draft']['mode'], 'new_party_member')
            self.assertEqual(pipeline.review_setup()['status'], 'character_review')
            self.assertEqual(pipeline.approve()['status'], 'open')
            state = RuntimeStateStore(root).load()
            self.assertEqual(state['main_character'], 'Kael')

    def test_stored_specialist_proposal_can_be_installed(self):
        with tempfile.TemporaryDirectory() as root:
            self._seed_open_campaign(root)
            RuntimeStateStore(root).save({'specialist_proposals': {'beast_taming': {'name': 'beast_taming', 'purpose': 'Tame beasts', 'questions': ['which'], 'activation_tags': ['activity.beast_taming']}}})
            pipeline = CampaignPipeline(root, modules=ScriptedGame())
            self.assertEqual([p['name'] for p in pipeline.specialist_proposals()], ['beast_taming'])
            review = pipeline.propose_specialist('beast_taming')
            self.assertEqual(review['status'], 'admin_review')
            self.assertEqual(pipeline.approve()['status'], 'open')
    def test_setup_chat_persists_player_message_when_model_is_unavailable(self):
        class OfflineChat(ScriptedGame):
            def setup_chat(self, draft, message):
                return {'status': 'fallback'}

        with tempfile.TemporaryDirectory() as root:
            RuntimeStateStore(root).save({'play_gate': 'setup_required'})
            pipeline = CampaignPipeline(root, modules=OfflineChat())
            pipeline.begin_setup()
            result = pipeline.submit('I want a quiet human ranger named Kael.')
            self.assertEqual(result['status'], 'setup_draft')
            state = RuntimeStateStore(root).load()
            self.assertEqual(state['draft']['conversation'][-1]['content'], 'I want a quiet human ranger named Kael.')
            self.assertIn('saved that message', state['message'])

    def test_setup_question_surfaces_and_resumes_same_draft(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'markdown_files').mkdir()
            Path(root, 'markdown_files/TEMP_MEMORY.md').write_text('before', encoding='utf-8')
            RuntimeStateStore(root).save({'play_gate': 'setup_required'})
            pipeline = CampaignPipeline(root, modules=ScriptedGame())
            pipeline.begin_setup()
            pipeline.add_character({'name': 'Kael', 'age': 24, 'race': 'Human'},
                                   {'AGI': 6, 'INT': 6, 'STR': 6, 'END': 6, 'WIS': 3, 'PRE': 3},
                                   'A frontier hunter.', 'Hunter')
            pipeline.select_main('Kael')
            review = pipeline.review_setup()
            self.assertEqual(review['status'], 'awaiting_clarification')
            self.assertIn('region', review['question']['question'])
            resumed = pipeline.submit('The northern frontier')
            self.assertEqual(resumed['status'], 'setup_review')


if __name__ == '__main__':
    unittest.main()
