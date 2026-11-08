import json
import tempfile
import unittest
from pathlib import Path

from brain.game_modules import GameModules


class WorldRulesTests(unittest.TestCase):
    def test_default_pool_covers_1_to_100_exactly_once(self):
        pool = GameModules._default_world_pool()
        flat = sorted(number for numbers in pool.values() for number in numbers)
        self.assertEqual(flat, list(range(1, 101)))
        self.assertEqual(sum(len(numbers) for numbers in pool.values()), 100)

    def test_inject_world_rules_scopes_event_engine_to_world_specialist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'brain/info').mkdir(parents=True)
            index = {'under': [{
                'name': 'game rules',
                'location': 'markdown_files/game rules (1).md',
                'under': [
                    {'name': 'Dynamic World Event Engine', 'location': 'lines 150-545', 'description': 'world event rules', 'under': []},
                    {'name': 'STAT SYSTEM', 'location': 'lines 1619-2400', 'description': 'stat rules', 'under': []},
                ],
            }]}
            (root / 'brain/info/evidence_index.json').write_text(json.dumps(index), encoding='utf-8')
            modules = GameModules(root)
            bundle = {'evidence_bundle': {'selected_sections': [], 'specialist_bundles': {}}}
            result = modules._inject_world_rules(bundle)
            world_sections = result['evidence_bundle']['specialist_bundles']['world']['selected_sections']
            self.assertEqual([section['name'] for section in world_sections], ['Dynamic World Event Engine'])
            self.assertNotIn('world-rule-', world_sections[0]['id'])
            self.assertEqual(
                result['evidence_bundle']['specialist_bundles']['world']['citation_allowlist']['evidence_ids'],
                [world_sections[0]['id']],
            )
            self.assertNotIn('STAT SYSTEM', [section['name'] for section in result['evidence_bundle']['selected_sections']])


if __name__ == '__main__':
    unittest.main()
