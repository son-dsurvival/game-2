import unittest
from pathlib import Path

from brain.setup_batches import batches


class SetupBatchTests(unittest.TestCase):
    def test_batches_are_defined_by_registered_templates(self):
        result = batches(Path(__file__).resolve().parents[1])
        self.assertEqual(len(result), 11)
        self.assertEqual(result[0]['id'], 'status_identity_stats_derived')
        self.assertIn('current XP / XP required', result[0]['purpose'])
        self.assertIn('Modifier Groups', result[6]['template_sections'])
        self.assertNotIn('world', result[6]['specialists'])
        self.assertEqual(result[-1]['file'], 'TEMP_MEMORY.md')


if __name__ == '__main__':
    unittest.main()
