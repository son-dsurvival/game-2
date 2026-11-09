import tempfile
import unittest
from pathlib import Path

from brain.evidence_bundle import EvidenceBundleBuilder


class EvidenceBundleHistoryTests(unittest.TestCase):
    def test_leaf_bundles_do_not_fall_back_to_full_history_or_terms(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'markdown_files').mkdir()
            (root / 'markdown_files' / 'game rules (1).md').write_text(
                '# Rules\n\n## Combat\n' + ('combat rule ' * 5000), encoding='utf-8'
            )
            (root / 'markdown_files' / 'TERMS_AND_NOMENCLATURE.md').write_text(
                '# Terms\n\n## Everything\n' + ('unrelated terminology ' * 5000), encoding='utf-8'
            )
            (root / 'brain' / 'state').mkdir(parents=True)
            (root / 'brain' / 'state' / 'player_prompt_history.txt').write_text(
                'Day 1 — Early Morning (0% through phase)\n\nPlayer:\n'
                + ('old unrelated history ' * 5000)
                + '\n\nGame:\nold result\n', encoding='utf-8'
            )
            route = {
                'turn_id': 'turn-budget',
                'request_type': 'in_game',
                'mode': 'combat',
                'tags': [{'tag': 'activity.combat'}],
                'required_specialists': ['combat', 'modifier'],
                'segments': [{'text': 'I punch the monster.', 'tags': ['activity.combat']}],
                'evidence_requests': [],
            }
            bundle = EvidenceBundleBuilder(root).build(
                route,
                player_input='I punch the monster.',
                current_state={'position': {'day': 1}, 'party': [], 'game_cache': {'large': 'x' * 50000}},
                selector='heuristic',
            ).to_dict()
            for name, scoped in bundle['specialist_bundles'].items():
                self.assertLessEqual(sum(len(section.get('text', '')) for section in scoped['selected_sections']), 14000)
                self.assertLessEqual(sum(len(str(item.get('text', ''))) for item in scoped['history']), 14000)
                self.assertNotIn('game_cache', scoped['state'])
            self.assertNotIn('TERMS_AND_NOMENCLATURE.md', '\n'.join(section['source'] for section in bundle['selected_sections']))

    def test_history_is_broken_down_and_scoped_for_specialists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'markdown_files').mkdir()
            (root / 'markdown_files' / 'status sheet.md').write_text(
                '# Character Status\n\n## Identity\n\n', encoding='utf-8'
            )
            (root / 'brain' / 'state').mkdir(parents=True)
            (root / 'brain' / 'state' / 'player_prompt_history.txt').write_text(
                'Day 1 — Early Morning (0% through phase)\n\n'
                'Player:\nFemi built an AI assistant named Ava.\n\n'
                'Game:\nThe setup record acknowledges Ava.\n\n',
                encoding='utf-8'
            )
            route = {
                'turn_id': 'turn-one',
                'request_type': 'in_game',
                'mode': 'noncombat',
                'tags': [],
                'required_specialists': ['character', 'rules'],
                'segments': [{'text': 'I use Ava to inspect the relay.'}],
            }
            bundle = EvidenceBundleBuilder(root).build(
                route,
                player_input='I use Ava to inspect the relay.',
                current_state={'position': {'day': 1}, 'party': [], 'game_cache': {}},
                selector='heuristic',
            ).to_dict()
            self.assertEqual(bundle['history_breakdown'][0]['history_id'], 'transcript-1')
            self.assertIn('system', bundle['history_breakdown'][0]['categories'])
            character_bundle = bundle['specialist_bundles']['character']
            self.assertEqual(len(character_bundle['history']), 1)
            self.assertIn('position', bundle['specialist_bundles']['rules']['state'])
            self.assertEqual(character_bundle['citation_allowlist']['history_ids'], ['transcript-1'])
            self.assertIn('all_ids', character_bundle['citation_allowlist'])
            self.assertEqual(
                set(character_bundle['citation_allowlist']['all_ids']),
                set(character_bundle['citation_allowlist']['evidence_ids']) | {'transcript-1'},
            )


if __name__ == '__main__':
    unittest.main()
