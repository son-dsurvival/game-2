import unittest
from pathlib import Path

from brain.game_modules import GameModules
from brain.setup_batches import batches, setup_changes_are_meaningful, starting_stat_modifier_slots


class SetupBatchTests(unittest.TestCase):
    def test_batches_are_defined_by_registered_templates(self):
        result = batches(Path(__file__).resolve().parents[1])
        self.assertEqual(len(result), 10)
        self.assertEqual(result[0]['id'], 'status_identity_stats_derived')
        self.assertIn('current XP / XP required', result[0]['purpose'])
        self.assertIn('three choices for every deterministic Stat Modifier slot', result[1]['purpose'])
        self.assertIn('five class-specific choices', result[2]['purpose'])
        self.assertFalse(any('Modifier Groups' in batch['template_sections'] for batch in result))
        self.assertFalse(any(batch['id'] == 'status_modifier_groups' for batch in result))
        self.assertEqual(result[-1]['file'], 'TEMP_MEMORY.md')

    def test_first_batch_preserves_empty_status_root_heading(self):
        normalized = GameModules._normalize_setup_change({
            'target_file': 'markdown_files/status sheet.md',
            'old_text': '# Character Status\n\nNo characters have been established for this new game yet.',
            'new_text': '# Femi Dsurvival\n\n## Identity\n',
        }, 'status_identity_stats_derived', 'status sheet.md')
        self.assertTrue(normalized['new_text'].startswith('# Character Status\n\n# Femi Dsurvival'))

    def test_targeted_setup_recovery_drops_obsolete_modifier_groups(self):
        cleaned = GameModules._clean_setup_change({
            'target_file': 'markdown_files/status sheet.md',
            'new_text': '### Effect Modifiers\n\nPlacement group: Stress Control\nPlacement defense: old taxonomy\n',
            'values': {'modifier_groups': 'legacy'},
        }, 'status_effect_modifiers')
        self.assertNotIn('Placement group', cleaned['new_text'])
        self.assertNotIn('modifier_groups', cleaned['values'])
        self.assertIsNone(GameModules._clean_setup_change({}, 'status_modifier_groups'))

    def test_empty_active_skill_sections_are_skipped_as_noop(self):
        changes = [{
            'old_text': 'Class ending\n\n---\n\n# Dara Adeyemi',
            'new_text': 'Class ending\n\n### Active Skills\n\nNo active system skills established.\n\n---\n\n# Dara Adeyemi',
        }]
        self.assertFalse(setup_changes_are_meaningful('status_active_skills', changes))
        changes[0]['new_text'] += '\n### Active Skills\n\n- Tracking'
        self.assertTrue(setup_changes_are_meaningful('status_active_skills', changes))

    def test_stat_modifier_slots_follow_stat_value_bands(self):
        slots = starting_stat_modifier_slots({
            'characters': [{
                'identity': {'name': 'Femi'},
                'stats': {'STR': 3, 'AGI': 5, 'INT': 10, 'WIS': 20},
            }]
        })
        self.assertEqual([(item['stat'], item['slot']) for item in slots], [
            ('AGI', 1), ('INT', 1), ('INT', 2),
            ('WIS', 1), ('WIS', 2), ('WIS', 3),
        ])


if __name__ == '__main__':
    unittest.main()
