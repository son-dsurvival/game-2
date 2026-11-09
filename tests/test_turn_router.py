import unittest

from brain.turn_router import TurnRouter


class TurnDiscussionRoutingTests(unittest.TestCase):
    def test_in_world_discussion_routes_leaf_character_roles_only(self):
        router = TurnRouter('.', require_git=False)
        result = router.route(
            'I talk to Dara about whether we should enter the dungeon.',
            campaign_mode=True,
            classifier='heuristic',
            active_npcs=('Dara',),
        )

        self.assertEqual(result.process_type, 'in_world_discussion')
        self.assertNotIn('rules', result.required_specialists)
        self.assertNotIn('character', result.required_specialists)
        self.assertNotIn('special', result.required_specialists)
        self.assertNotIn('create', result.required_specialists)
        self.assertIn('current_state', result.required_specialists)
        self.assertIn('npc_autonomy', result.required_specialists)

    def test_social_discussion_adds_relationship_leaf(self):
        router = TurnRouter('.', require_git=False)
        result = router.route(
            'I ask Dara whether she trusts me before we leave.',
            campaign_mode=True,
            classifier='heuristic',
            active_npcs=('Dara',),
        )

        self.assertEqual(result.process_type, 'in_world_discussion')
        self.assertIn('relationship', result.required_specialists)
        self.assertIn('npc_autonomy', result.required_specialists)


if __name__ == '__main__':
    unittest.main()
