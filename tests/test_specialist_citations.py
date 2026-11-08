import unittest

from brain.specialists.runner import SpecialistRunner


class SpecialistCitationAllowlistTests(unittest.TestCase):
    def setUp(self):
        self.runner = SpecialistRunner('.')

    def test_validator_uses_the_explicit_allowlist(self):
        allowlist = {
            'evidence_ids': ['evidence-allowed'],
            'history_ids': ['transcript-allowed'],
            'all_ids': ['evidence-allowed', 'transcript-allowed'],
        }
        valid, invalid = self.runner._validate_citations(
            [
                {'evidence_id': 'evidence-allowed', 'claim': 'supported'},
                {'history_id': 'transcript-allowed', 'claim': 'supported'},
                {'evidence_id': 'evidence-not-supplied', 'claim': 'unsupported'},
            ],
            [],
            'cache',
            history=[],
            citation_allowlist=allowlist,
        )
        self.assertEqual([item.get('evidence_id') or item.get('history_id') for item in valid], [
            'evidence-allowed',
            'transcript-allowed',
        ])
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0]['type'], 'citation_outside_frozen_bundle')

    def test_legacy_line_range_is_not_accepted_when_not_allowlisted(self):
        valid, invalid = self.runner._validate_citations(
            [{'evidence_id': 'world-rule-game-rules-lines 180-198', 'claim': 'legacy'}],
            [],
            'world',
            citation_allowlist={
                'evidence_ids': ['canonical-world-section'],
                'history_ids': [],
                'all_ids': ['canonical-world-section'],
            },
        )
        self.assertEqual(valid, [])
        self.assertEqual(invalid[0]['type'], 'citation_outside_frozen_bundle')


if __name__ == '__main__':
    unittest.main()
