import unittest

from brain.game_runtime import _player_safe_change_preview


class ProposalPreviewTests(unittest.TestCase):
    def test_preview_hides_private_metadata_and_formulas(self):
        preview = _player_safe_change_preview({
            'new_text': (
                '# Femi Dsurvival\n\n'
                '## Stats\n'
                'HP = END × 5 = 20\n'
                'STR: 3\n'
                'Reason: private admin explanation\n'
                'Evidence: transcript-3\n'
            )
        })
        self.assertIn('# Femi Dsurvival', preview)
        self.assertIn('HP: 20', preview)
        self.assertIn('STR: 3', preview)
        self.assertNotIn('Reason: private admin explanation', preview)
        self.assertNotIn('Evidence: transcript-3', preview)
        self.assertFalse(any('=' in line for line in preview))

    def test_preview_is_player_safe_when_text_is_missing(self):
        preview = _player_safe_change_preview({'new_text': ''})
        self.assertEqual(len(preview), 1)
        self.assertIn('no readable preview', preview[0])


if __name__ == '__main__':
    unittest.main()
