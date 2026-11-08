import unittest

from brain.player_clarification import PlayerClarification


class PlayerClarificationTests(unittest.TestCase):
    def test_translates_safe_question_from_complete_admin_response(self):
        result = PlayerClarification.present({
            'status': 'needs_clarification',
            'answer': 'Internal evidence is sufficient.',
            'diagnosis': {'issue': 'private template detail'},
            'questions': ['Should Dara remain classless?'],
            'conflicts': [{'type': 'internal'}],
        })
        self.assertEqual(result, {
            'question': 'Should Dara remain classless?',
            'source': 'player_clarification',
        })

    def test_rejects_internal_admin_question(self):
        result = PlayerClarification.present({
            'status': 'needs_clarification',
            'questions': ['Provide the exact current status sheet and registered template.'],
        })
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
