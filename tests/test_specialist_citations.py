import unittest

from brain.specialists.runner import SpecialistRunner
from brain.specialists.registry import get_specialist


class SpecialistCitationAllowlistTests(unittest.TestCase):
    def setUp(self):
        self.runner = SpecialistRunner('.')

    def test_runner_injects_registry_task_prompt_into_system_contract(self):
        definition = get_specialist('world')
        prompt = self.runner._system_prompt(definition)
        self.assertIn('Registry-owned specialist contract', prompt)
        self.assertIn('world-event and world-pool mechanics', prompt)
        self.assertIn('Do not place world-event work in another specialist', prompt)

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

    def test_stat_modifier_options_are_three_per_eligible_slot(self):
        definition = get_specialist('create_stat_modifier')

        def option(stat, index):
            return {
                'name': f'{stat} option {index}', 'stat': stat, 'tier': 0,
                'breadth': 'broad_stat_domain',
                'basis_level': 'low', 'major_or_minor': 'minor',
                'magnitude': '+1', 'description': 'bounded option',
                'evidence': ['player draft'], 'limitations': 'narrow use',
                'growth_or_conversion_rule': 'requires later confirmation',
            }

        result = self.runner._validate_result(
            {
                'specialist': 'create_stat_modifier', 'status': 'complete',
                'citations': [], 'applicable_rules': [], 'excluded_rules': [],
                'findings': [], 'assumptions': [], 'evidence_requests': [],
                'conflicts': [], 'recommendation': None,
                'stat_modifier_options': [option('INT', i) for i in range(3)]
                              + [option('WIS', i) for i in range(3)],
            }, definition, [], history=[], citation_allowlist={'evidence_ids': [], 'history_ids': []}
        )
        self.assertEqual(result['status'], 'complete')

    def test_stat_modifier_validator_rejects_missing_broad_domain_declaration(self):
        definition = get_specialist('create_stat_modifier')
        options = [{
            'name': f'option {i}', 'stat': 'INT', 'tier': 0, 'basis_level': 'low',
            'major_or_minor': 'minor', 'magnitude': '+1',
            'description': 'analysis generally', 'evidence': ['player draft'],
            'limitations': 'bounded', 'growth_or_conversion_rule': 'later confirmation',
        } for i in range(3)]
        result = self.runner._validate_result(
            {
                'specialist': 'create_stat_modifier', 'status': 'complete',
                'citations': [], 'applicable_rules': [], 'excluded_rules': [],
                'findings': [], 'assumptions': [], 'evidence_requests': [],
                'conflicts': [], 'recommendation': None,
                'stat_modifier_options': options,
            }, definition, [], history=[], citation_allowlist={'evidence_ids': [], 'history_ids': []}
        )
        self.assertEqual(result['status'], 'needs_evidence')
        self.assertIn('incomplete_modifier_options', [item['type'] for item in result['conflicts']])

    def test_stat_modifier_validator_rejects_five_total_choices_across_stats(self):
        definition = get_specialist('create_stat_modifier')
        options = [{
            'name': f'option {i}', 'stat': stat, 'tier': 0, 'breadth': 'broad_stat_domain',
            'basis_level': 'low', 'major_or_minor': 'minor', 'magnitude': '+1',
            'description': 'bounded option', 'evidence': ['player draft'],
            'limitations': 'narrow use', 'growth_or_conversion_rule': 'later confirmation',
        } for i, stat in enumerate(['STR', 'AGI', 'END', 'INT', 'WIS'])]
        result = self.runner._validate_result(
            {
                'specialist': 'create_stat_modifier', 'status': 'complete',
                'citations': [], 'applicable_rules': [], 'excluded_rules': [],
                'findings': [], 'assumptions': [], 'evidence_requests': [],
                'conflicts': [], 'recommendation': None,
                'stat_modifier_options': options,
            }, definition, [], history=[], citation_allowlist={'evidence_ids': [], 'history_ids': []}
        )
        self.assertEqual(result['status'], 'needs_evidence')
        self.assertIn('invalid_modifier_option_group_count', [item['type'] for item in result['conflicts']])

    def test_starting_effect_modifiers_require_ten_choices(self):
        definition = get_specialist('create_effect_modifier')

        def option(index):
            return {
                'name': f'option {index}',
                'basis_level': 'assumed_low', 'tier': 0, 'magnitude': '+1',
                'description': 'bounded effect', 'boost_domain': '+1 narrow use',
                'evidence': ['character description'],
                'activation_conditions': 'when the described condition exists',
                'limitations': 'narrow and tier-bound',
                'anti_farming_boundary': 'no repetition farming',
                'stacking': 'follow explicit rules only',
                'placements': [{
                    'group': 'Test', 'use_in_group': True,
                    'activation_conditions': 'condition', 'limitations': 'narrow',
                    'stacking': 'explicit rules only', 'evidence': 'description',
                    'placement_reason': 'bounded',
                }],
            }

        result = self.runner._validate_result(
            {
                'specialist': 'create_effect_modifier', 'status': 'complete',
                'citations': [], 'applicable_rules': [], 'excluded_rules': [],
                'findings': [], 'assumptions': [], 'evidence_requests': [],
                'conflicts': [], 'recommendation': None,
                'effect_modifier_options': [option(i) for i in range(10)],
            }, definition, [], history=[], citation_allowlist={'evidence_ids': [], 'history_ids': []},
            setup_batch_id='status_effect_modifiers',
        )
        self.assertEqual(result['status'], 'complete')

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
