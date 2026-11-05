import tempfile
import unittest
from pathlib import Path

from brain.game_modules import GameModules
from brain.runtime_state import RuntimeStateStore
from brain.setup_drafts import SetupDrafts


class PartyDirectiveTests(unittest.TestCase):
    def test_only_non_main_party_members_get_autonomy_directives(self):
        context = {
            'main_character': 'Kael',
            'party': [
                {'identity': {'name': 'Kael'}},
                {'identity': {'name': 'Renn'}},
                {'identity': {'name': 'Mira'}},
            ],
        }
        directives = GameModules._party_directives(context)
        self.assertEqual(sorted(d['actor'] for d in directives), ['Mira', 'Renn'])
        for directive in directives:
            self.assertTrue(directive['directive_id'].startswith('party-'))
            self.assertTrue(directive['metadata']['party_member'])
            self.assertEqual(directive['metadata']['visibility'], 'hidden')

    def test_no_party_yields_no_directives(self):
        self.assertEqual(GameModules._party_directives({}), [])


class SpecialistInstallTests(unittest.TestCase):
    def test_install_registers_branch_in_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'markdown_files').mkdir()
            (root / 'markdown_files/Branch Registry.md').write_text(
                '# Branch Registry\n\n## Business\nstatus: locked\nspecialist: business\n\n## Unlock Rules\n\nA branch becomes unlocked only when established.\n',
                encoding='utf-8',
            )
            modules = GameModules(root)
            proposal = modules.prepare_specialist_install({}, {
                'name': 'beast_taming',
                'purpose': 'Track, calm, and tame wild beasts.',
                'questions': ['Which beast is being tamed?'],
                'activation_tags': ['activity.beast_taming'],
            })
            self.assertEqual(proposal['status'], 'proposal_ready')
            updated = proposal['changes'][0]['new_text']
            self.assertIn('## Beast Taming', updated)
            self.assertIn('specialist: beast_taming', updated)
            self.assertIn('activation tags: activity.beast_taming', updated)
            # The Unlock Rules section is preserved after the new branch.
            self.assertLess(updated.index('## Beast Taming'), updated.index('## Unlock Rules'))

    def test_install_rejects_duplicate_or_unsafe_specialist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'markdown_files').mkdir()
            (root / 'markdown_files/Branch Registry.md').write_text('# Branch Registry\n', encoding='utf-8')
            modules = GameModules(root)
            with self.assertRaises(ValueError):
                modules.prepare_specialist_install({}, {'name': 'rules', 'purpose': 'dup', 'questions': ['q'], 'activation_tags': []})
            with self.assertRaises(ValueError):
                modules.prepare_specialist_install({}, {'name': 'Bad Name', 'purpose': 'x', 'questions': ['q'], 'activation_tags': []})


class CharacterModeTests(unittest.TestCase):
    def test_mid_campaign_addition_requires_open_play(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RuntimeStateStore(directory)
            store.save({'play_gate': 'setup_required'})
            with self.assertRaises(RuntimeError):
                SetupDrafts(store).begin('new_character')
            store.save({'play_gate': 'open', 'campaign_id': 'campaign-one'})
            SetupDrafts(store).begin('new_character')
            state = store.load()
            self.assertEqual(state['draft']['mode'], 'new_character')
            self.assertEqual(state['draft']['campaign_id'], 'campaign-one')
            self.assertEqual(state['draft']['main_character'], None)
            store.save({'main_character': 'Kael', 'play_gate': 'open', 'draft': None, 'operation': None})
            SetupDrafts(store).begin('new_party_member')
            self.assertEqual(store.load()['draft']['main_character'], 'Kael')

    def test_chat_setup_accumulates_natural_language_patches_before_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RuntimeStateStore(directory)
            store.save({'play_gate': 'setup_required'})
            drafts = SetupDrafts(store)
            drafts.begin('new_game')
            drafts.apply_chat({'user_message': 'I want Kael, a human frontier hunter.',
                                'assistant_message': 'What age and starting stats should Kael have?',
                                'complete': False,
                                'draft': {'identity': {'name': 'Kael', 'race': 'Human'},
                                          'description': 'A frontier hunter.', 'class': 'Hunter'}})
            drafts.apply_chat({'user_message': 'He is 24. Use AGI 6 INT 6 STR 6 END 6 WIS 3 PRE 3.',
                                'assistant_message': 'Kael is ready.', 'complete': True,
                                'draft': {'identity': {'age': 24},
                                          'stats': {'AGI': 6, 'INT': 6, 'STR': 6, 'END': 6, 'WIS': 3, 'PRE': 3}}})
            state = store.load()
            self.assertEqual(state['draft']['characters'][0]['identity']['name'], 'Kael')
            self.assertEqual(state['draft']['characters'][0]['stats']['STR'], 6)
            drafts.apply_chat({'user_message': 'We are done; Femi is the main character.',
                                'assistant_message': 'The party is ready for review.',
                                'complete': False, 'party_done': True, 'main_character': 'Kael', 'draft': {}})
            state = store.load()
            self.assertEqual(state['draft']['main_character'], 'Kael')
            self.assertTrue(state['draft']['party_done'])

    def test_mid_campaign_addition_takes_one_character_at_a_time(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RuntimeStateStore(directory)
            store.save({'play_gate': 'open', 'campaign_id': 'campaign-one'})
            drafts = SetupDrafts(store)
            drafts.begin('new_party_member')
            drafts.add({'name': 'Renn', 'age': 31, 'race': 'Human'},
                       {'AGI': 5, 'INT': 5, 'STR': 5, 'END': 5, 'WIS': 5, 'PRE': 5},
                       'A road-worn traveler.', 'Scout')
            with self.assertRaises(ValueError):
                drafts.another()


if __name__ == '__main__':
    unittest.main()
