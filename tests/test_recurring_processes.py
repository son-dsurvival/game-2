import json
import tempfile
import unittest
from pathlib import Path

from backend.contracts import PhasePosition
from backend.world_director import WorldDirector


class WorldDirectorProcessTests(unittest.TestCase):
    def test_formula_writer_creates_catalog_used_by_planning(self):
        with tempfile.TemporaryDirectory() as root:
            engine = WorldDirector(root)
            engine.upsert_formula('daily_water', {
                'type': 'regeneration',
                'resource_changes': [{'resource': 'water', 'delta': 2}],
            })
            self.assertEqual(engine.load_formulas()['daily_water']['type'], 'regeneration')
            self.assertTrue((Path(root) / 'brain/state/resource_formulas.json').exists())

    def test_due_process_loads_formula_checks_requirements_and_calculates_changes(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            state = root / 'brain/state/recurring_processes.json'
            formulas = root / 'brain/state/resource_formulas.json'
            state.parent.mkdir(parents=True)
            state.write_text(json.dumps({'processes': [{
                'id': 'smelter', 'status': 'active', 'process_type': 'production',
                'formula_id': 'iron_ingot',
                'next_due': {'day': 1, 'phase': 'Morning', 'progress': 0},
                'cadence_phases': 2,
                'requirements': [{'kind': 'facility', 'name': 'smelter'}],
            }]}), encoding='utf-8')
            formulas.write_text(json.dumps({'formulas': {'iron_ingot': {
                'type': 'transformation',
                'inputs': [{'resource': 'ore', 'amount': 2}],
                'outputs': [{'resource': 'ingot', 'amount': 1}],
            }}}), encoding='utf-8')
            engine = WorldDirector(root)
            plan = engine.plan_processes(
                PhasePosition(1, 'Early Morning'),
                PhasePosition(1, 'Morning'),
                context={'facilities': ['smelter']},
            )
            self.assertEqual(plan['due_count'], 1)
            process = plan['processes'][0]
            self.assertEqual(process['process_type'], 'production')
            self.assertTrue(process['eligible'])
            self.assertEqual(
                process['calculated_changes'],
                [
                    {'resource': 'ore', 'delta': -2, 'per_cycle': -2.0, 'cycles': 1},
                    {'resource': 'ingot', 'delta': 1, 'per_cycle': 1.0, 'cycles': 1},
                ],
            )

    def test_run_sends_resources_then_backend_and_commits_only_after_resolution(self):
        with tempfile.TemporaryDirectory() as root:
            engine = WorldDirector(root)
            engine.upsert_process({
                'id': 'regen', 'status': 'active', 'process_type': 'regeneration',
                'next_due': {'day': 1, 'phase': 'Morning', 'progress': 0},
                'formula': {'resource_changes': [{'resource': 'mana', 'delta': 3}]},
            })
            calls = []

            def resources(plan, context):
                calls.append('resources')
                return {'specialist': 'resources', 'accepted_candidates': plan['processes']}

            def backend(plan, context):
                calls.append('backend')
                self.assertIn('resource_specialist', plan)
                return {
                    'status': 'resolved',
                    'resource_changes': [{'resource': 'mana', 'delta': 3}],
                    'process_results': [{'process_id': 'regen', 'status': 'applied', 'reason': 'validated'}],
                }

            result = engine.run_processes(
                PhasePosition(1, 'Early Morning'),
                PhasePosition(1, 'Morning'),
                resource_specialist=resources,
                backend_lead_resolver=backend,
            )
            self.assertEqual(calls, ['resources', 'backend'])
            self.assertEqual(result['status'], 'complete')
            self.assertEqual(engine.load_processes()[0]['last_processed_tick'], 'process-1-Morning-0')

    def test_unsatisfied_requirements_are_not_eligible(self):
        with tempfile.TemporaryDirectory() as root:
            engine = WorldDirector(root)
            engine.upsert_process({
                'id': 'pump', 'status': 'active',
                'next_due': {'day': 1, 'phase': 'Morning', 'progress': 0},
                'requirements': [{'kind': 'resource', 'resource': 'fuel', 'amount': 2}],
                'formula': {'resource_changes': [{'resource': 'water', 'delta': 5}]},
            })
            plan = engine.plan_processes(PhasePosition(1, 'Early Morning'), PhasePosition(1, 'Morning'))
            self.assertFalse(plan['processes'][0]['eligible'])
            self.assertEqual(plan['processes'][0]['requirement_check']['missing'][0]['resource'], 'fuel')


if __name__ == '__main__':
    unittest.main()
