import unittest

from brain.specialists.branch_registry import BranchRegistry
from brain.specialists.character_group import character_specialist_group
from brain.specialists.registry import SPECIALIST_DEFINITIONS


class CharacterGroupTests(unittest.TestCase):
    def test_main_character_receives_reduced_character_specialists(self):
        groups = character_specialist_group({
            'identity': {'name': 'Femi Dsurvival'},
            'description': 'engineer and housemate',
        }, role='player')
        by_key = {item['group_key']: item for item in groups}
        self.assertEqual(set(by_key), {'stats', 'actions_effects', 'class', 'active_skills_spells'})
        self.assertNotIn('identity_behavior', by_key)
        self.assertNotIn('social_autonomy', by_key)
        self.assertEqual(by_key['active_skills_spells']['base_specialists'], ['active_skills_spells', 'class'])
        self.assertEqual(len(groups), 4)

    def test_party_receives_identity_social_and_active_skill_specialists(self):
        groups = character_specialist_group({
            'identity': {'name': 'Dara Adeyemi'},
            'description': 'athlete and housemate',
        }, role='party')
        by_key = {item['group_key']: item for item in groups}
        self.assertEqual(by_key['stats']['specialists'], ['character_dara_adeyemi_stats'])
        self.assertEqual(by_key['stats']['base_specialists'], ['modifier', 'create_stat_modifier'])
        self.assertEqual(by_key['actions_effects']['specialists'], ['character_dara_adeyemi_actions_effects'])
        self.assertEqual(by_key['social_autonomy']['base_specialists'], ['relationship', 'npc_autonomy'])
        self.assertEqual(len(groups), 6)
        self.assertIn('Dara Adeyemi', groups[0]['prompt'])
        self.assertIn('dedicated', groups[0]['prompt'])

    def test_global_progression_reward_specialists_and_tier_six_branch_exist(self):
        self.assertIn('tier_level_up', SPECIALIST_DEFINITIONS)
        self.assertIn('consumables_rewards', SPECIALIST_DEFINITIONS)
        tier_six = BranchRegistry('.').entry('tier_6')
        self.assertIsNotNone(tier_six)
        self.assertEqual(tier_six['status'], 'candidate')
        self.assertEqual(tier_six['specialist'], 'tier_6')

    def test_non_party_character_receives_reduced_durable_set(self):
        groups = character_specialist_group({
            'identity': {'name': 'A Visitor'},
            'description': 'a recurring stranger',
        }, role='non_party')
        self.assertEqual([item['group_key'] for item in groups], [
            'identity_behavior', 'actions_effects', 'social_autonomy',
        ])
        self.assertTrue(all(item['character_role'] == 'non_party' for item in groups))
        self.assertTrue(all(item['registry_name'].startswith('character_a_visitor_') for item in groups))


if __name__ == '__main__':
    unittest.main()
