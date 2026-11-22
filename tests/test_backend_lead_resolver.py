import unittest
from unittest.mock import patch

from backend.backend_lead_resolver import BackendLeadResolver


class BackendLeadResolverTests(unittest.TestCase):
    def test_backend_resolver_preserves_answered_clarification_link(self):
        linked = {
            'id': 'turn:clarification:1', 'status': 'answered',
            'question': 'How many herbs?', 'answer': 'You decide',
            'result': {'candidate_options': ['one', 'two', 'three']},
        }
        with patch('brain.backend_lead_resolver.AssumptionWizard.maybe_create', return_value=None), \
             patch('brain.backend_lead_resolver.LeadResolver.resolve', return_value={'status': 'resolved'}) as resolve:
            BackendLeadResolver('.').resolve(
                {'coverage_check': {'ready_for_lead_resolver': True}},
                plan={'tick_id': 'day-1-morning', 'actions': []},
                context={'answers': ['You decide'], 'active_clarification': linked},
            )
        kwargs = resolve.call_args.kwargs
        self.assertEqual(kwargs['campaign_context']['clarification_continuation'], linked)
        self.assertEqual(kwargs['chat_context']['active_clarification'], linked)

    def test_backend_resolver_reuses_provisional_assumption_across_ticks(self):
        assumption_record = {'status': 'provisional', 'name': 'rate', 'default_value': 1}
        with patch('brain.backend_lead_resolver.AssumptionWizard.maybe_create', side_effect=AssertionError('must reuse existing assumption')):
            with patch('brain.backend_lead_resolver.LeadResolver.resolve', return_value={'status': 'resolved'}) as resolve:
                BackendLeadResolver('.').resolve(
                    {'coverage_check': {'ready_for_lead_resolver': True}},
                    plan={'tick_id': 'day-1-late-morning', 'actions': []},
                    context={'assumption_record': assumption_record},
                )
        self.assertEqual(resolve.call_args.kwargs['campaign_context']['assumption_record'], assumption_record)

    def test_backend_resolver_owns_hidden_decision_boundary(self):
        expected = {'status': 'resolved', 'resolution_record': {'background_packet': {'actions': []}}}
        with patch('brain.backend_lead_resolver.AssumptionWizard.maybe_create', return_value=None) as assumption, \
             patch('brain.backend_lead_resolver.LeadResolver.resolve', return_value=expected) as resolve:
            result = BackendLeadResolver('.').resolve(
                {'coverage_check': {'ready_for_lead_resolver': True}},
                plan={'tick_id': 'day-1-morning', 'actions': []},
                context={'answers': [], 'private_background': []},
            )

        self.assertEqual(result, expected)
        assumption.assert_called_once()
        kwargs = resolve.call_args.kwargs
        self.assertTrue(kwargs['campaign_context']['backend_autonomy'])
        self.assertTrue(kwargs['campaign_context']['private_background'])
        self.assertEqual(kwargs['campaign_context']['backend_plan']['tick_id'], 'day-1-morning')


if __name__ == '__main__':
    unittest.main()
