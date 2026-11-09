import unittest

from brain.assumption_wizard import AssumptionWizard


class AssumptionWizardTests(unittest.TestCase):
    def test_requires_explicit_player_delegation(self):
        self.assertTrue(AssumptionWizard.permission_granted(['You decide.']))
        self.assertFalse(AssumptionWizard.permission_granted(['Please explain the rule.']))

    def test_accepts_only_bounded_provisional_assumptions(self):
        value = AssumptionWizard.validate({
            'status': 'provisional',
            'assumption_type': 'initialization_seed',
            'name': 'starting_fuel',
            'statement': 'Use a conservative starting fuel quantity.',
            'procedure': 'Track fuel in liters and reduce it only when consumed.',
            'default_value': 40,
            'scope': 'current_entity',
            'basis': ['ordinary compact-car baseline'],
            'limitations': ['Do not imply unlimited fuel.'],
            'confidence': 'medium',
            'review_trigger': 'Inspect the vehicle record or refuel it.',
        })
        self.assertEqual(value['status'], 'provisional')
        self.assertEqual(value['persistence'], 'temporary_memory')
        self.assertTrue(value['player_authorized'])

    def test_rejects_campaign_scope(self):
        value = AssumptionWizard.validate({
            'status': 'provisional',
            'assumption_type': 'provisional_rule',
            'name': 'collision',
            'statement': 'A collision uses mass and speed.',
            'procedure': 'Apply it now.',
            'scope': 'campaign',
            'basis': ['rules gap'],
            'limitations': ['temporary'],
            'review_trigger': 'Repeated use.',
        })
        self.assertEqual(value['status'], 'blocked')

    def test_gap_detection_requires_a_missing_mechanism(self):
        context = {
            'answers': ['You decide.'],
            'pending_clarification': {'question': 'There is no collision mechanism.'},
        }
        self.assertIsNotNone(AssumptionWizard.gap_request(context, {'specialist_results': []}))
        self.assertIsNone(AssumptionWizard.gap_request({'answers': ['You decide.']}, {'specialist_results': []}))


if __name__ == '__main__':
    unittest.main()
