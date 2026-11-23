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

    def test_combat_profile_adds_baseline_analysis_without_optional_spell_or_resource(self):
        router = TurnRouter('.', require_git=False)
        result = router.route(
            'I attack the wolf with my sword.',
            campaign_mode=True,
            classifier='heuristic',
        )
        self.assertTrue({'combat', 'difficulty', 'time', 'modifier'} <= set(result.required_specialists))
        self.assertNotIn('spell', result.required_specialists)
        self.assertNotIn('resources', result.required_specialists)
        self.assertNotIn('create_effect_modifier', result.required_specialists)

    def test_experiment_profile_adds_difficulty_and_time(self):
        router = TurnRouter('.', require_git=False)
        result = router.route(
            'I experiment with the relay wiring.',
            campaign_mode=True,
            classifier='heuristic',
        )
        self.assertTrue({'experimentation', 'difficulty', 'time'} <= set(result.required_specialists))

    def test_xp_and_reward_profiles_route_progression_and_bookkeeping(self):
        router = TurnRouter('.', require_git=False)
        xp = router.route('I gain enough XP to level up.', campaign_mode=True, classifier='heuristic')
        reward = router.route('I use a healing consumable.', campaign_mode=True, classifier='heuristic')
        self.assertTrue({'xp', 'tier_level_up'} <= set(xp.required_specialists))
        self.assertIn('consumables_rewards', reward.required_specialists)

    def test_situation_conditions_route_situation_specialist(self):
        router = TurnRouter('.', require_git=False)
        result = router.route(
            'I cross the wet, dark terrain while visibility is poor.',
            campaign_mode=True,
            classifier='heuristic',
        )
        self.assertIn('situation', result.required_specialists)

    def test_registered_character_groups_replace_broad_character_route(self):
        from brain.specialists.character_group import character_specialist_group

        groups = character_specialist_group({
            'identity': {'name': 'Dara Adeyemi'},
            'description': 'athlete and housemate',
        })
        router = TurnRouter('.', require_git=False)
        result = router.route(
            'Dara inspects the home gym and discusses the next training plan.',
            campaign_mode=True,
            classifier='heuristic',
            current_state={'character_specialist_groups': {'Dara Adeyemi': groups}},
        )

        self.assertNotIn('character', result.required_specialists)
        self.assertIn('character_dara_adeyemi_identity_behavior', result.required_specialists)
        self.assertIn('character_dara_adeyemi_actions_effects', result.required_specialists)

    def test_backend_autonomy_uses_backend_process_and_explicit_specialists(self):
        router = TurnRouter('.', require_git=False)
        result = router.route(
            'Resolve Renn collecting herbs in the north grove.',
            campaign_mode=True,
            classifier='heuristic',
            current_state={
                'backend_autonomy': True,
                'backend_required_specialists': ['rules', 'character'],
            },
        )

        self.assertEqual(result.request_type, 'backend_autonomy')
        self.assertEqual(result.process_type, 'backend_autonomy')
        self.assertEqual(result.required_specialists, [])

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
