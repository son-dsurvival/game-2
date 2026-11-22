import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'outside game'))
from admin_agent import AdminAgent  # noqa: E402


class AdminValidationTests(unittest.TestCase):
    def test_empty_modifier_group_section_is_not_a_placement(self):
        result = AdminAgent._validate({
            'status': 'proposal_ready',
            'answer': 'The section is intentionally empty.',
            'diagnosis': {'issue': 'empty setup section', 'why': 'no effects selected'},
            'evidence': [],
            'changes': [{
                'target_file': 'markdown_files/status sheet.md',
                'action': 'update',
                'values': {'modifier_groups': 'No Effect Modifier placements are recorded.'},
                'new_text': (
                    '### Modifier Groups\n\n'
                    'No Effect Modifier placements are recorded.\n\n'
                    'This section is intentionally empty during setup.'
                ),
            }],
            'instructions': [],
            'questions': [],
            'conflicts': [],
            'modifier_group_placements': [],
            'approval_required': True,
        }, 'setup-test')
        self.assertEqual(result['status'], 'proposal_ready')


if __name__ == '__main__':
    unittest.main()
