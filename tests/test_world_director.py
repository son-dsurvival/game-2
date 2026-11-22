import tempfile
import unittest
from pathlib import Path

from backend.contracts import PhasePosition
from backend.world_director import WorldDirector


class WorldDirectorTests(unittest.TestCase):
    def test_growth_and_event_schedule_are_private_and_replayable(self):
        with tempfile.TemporaryDirectory() as directory:
            director = WorldDirector(directory)
            state_path = Path(directory) / 'brain/state/world_state.json'
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                '{"schema_version": 1, "entities": {"goblins": {'
                '"population": 10, "growth_per_day": 5, "capacity": 30, '
                '"event_threshold": 15, "event_template": "The colony expands."'
                '}}, "scheduled_events": [], "history": []}',
                encoding='utf-8',
            )
            plan = director.advance(
                PhasePosition(1, 'Early Morning'),
                PhasePosition(2, 'Early Morning'),
            )
            self.assertEqual(plan['entity_updates'][0]['after']['population'], 15)
            self.assertTrue(plan['event_design_requested'])
            committed = director.commit(plan)
            self.assertEqual(committed['status'], 'committed')
            self.assertEqual(committed['pending_world_event']['day'], 2)
            self.assertEqual(director.due_event(PhasePosition(2, 'Midday'))['status'], 'scheduled')

    def test_apply_entity_changes_is_typed_atomic_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            director = WorldDirector(directory)
            director.upsert_entity({'id': 'forest_goblins', 'population': 20, 'capacity': 100})
            result = director.apply_entity_changes({
                'change_id': 'turn-123:goblin-kills',
                'entity_id': 'forest_goblins',
                'field': 'population',
                'delta': -30,
                'reason': '30 goblins killed',
                'visibility': 'visible',
            })
            self.assertEqual(result['changes'][0]['before'], 20)
            self.assertEqual(result['changes'][0]['after'], 0)
            with self.assertRaises(ValueError):
                director.apply_entity_changes({
                    'change_id': 'turn-123:goblin-kills',
                    'entity_id': 'forest_goblins', 'field': 'population',
                    'delta': -1, 'reason': 'duplicate',
                })
            with self.assertRaises(ValueError):
                director.apply_entity_changes({
                    'change_id': 'turn-124:bad-field',
                    'entity_id': 'forest_goblins', 'field': 'unknown',
                    'delta': 1, 'reason': 'unsupported',
                })

    def test_commit_applies_growth_then_resolved_entity_change(self):
        with tempfile.TemporaryDirectory() as directory:
            director = WorldDirector(directory)
            director.upsert_entity({
                'id': 'forest_goblins', 'population': 20,
                'growth_per_day': 20, 'capacity': 100,
            })
            plan = director.advance(
                PhasePosition(1, 'Early Morning'),
                PhasePosition(3, 'Early Morning'),
            )
            committed = director.commit(plan, resolution={
                'status': 'resolved',
                'world_entity_changes': [{
                    'change_id': 'turn-123:goblin-kills',
                    'entity_id': 'forest_goblins',
                    'field': 'population',
                    'delta': -30,
                    'reason': '30 confirmed kills',
                }],
            })
            self.assertEqual(committed['entity_changes'][0]['before'], 60)
            self.assertEqual(committed['entity_changes'][0]['after'], 30)
            self.assertEqual(director.load()['entities']['forest_goblins']['population'], 30)

    def test_event_design_updates_the_private_scheduled_event(self):
        with tempfile.TemporaryDirectory() as directory:
            director = WorldDirector(directory)
            plan = director.advance(
                PhasePosition(1, 'Early Morning'),
                PhasePosition(2, 'Early Morning'),
                context={'world_entities': [{
                    'id': 'wolves', 'population': 10, 'growth_per_day': 1,
                    'event_threshold': 11, 'event_key': 'wolves-pressure',
                }]},
            )
            director.commit(plan, resolution={
                'world_event': {
                    'event_key': 'wolves-pressure',
                    'generated_event': 'The wolves begin hunting travelers.',
                    'encounter_condition': 'The player travels through the north road.',
                    'latest_phase': 'Evening',
                    'observable_signs': ['tracks'],
                }
            })
            event = director.due_event(PhasePosition(2, 'Evening'))
            self.assertEqual(event['generated_event'], 'The wolves begin hunting travelers.')
            self.assertEqual(event['observable_signs'], ['tracks'])


if __name__ == '__main__':
    unittest.main()
