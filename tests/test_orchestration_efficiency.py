import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brain.game_modules import GameModules
from brain.specialists.coverage_check import CoverageCheck


class OrchestrationEfficiencyTests(unittest.TestCase):
    def test_setup_batches_do_not_force_normal_turn_core(self):
        with tempfile.TemporaryDirectory() as directory:
            modules = GameModules(Path(directory))
            fake_result = {
                'specialist_results': [],
                'coverage': {'required': ['rules', 'character']},
                'mandatory_specialists': [],
            }
            with patch('brain.game_modules.SpecialistRunner') as runner_type:
                runner_type.return_value.run.return_value = fake_result
                modules.specialists(
                    {'required_specialists': ['cache', 'rules', 'character', 'special', 'create']},
                    {'setup_batch_specialists': ['rules', 'character']},
                    ('character',),
                )
                call = runner_type.return_value.run.call_args
                self.assertEqual(call.args[1], ['rules', 'character'])
                self.assertEqual(call.kwargs['mandatory_specialists'], ())

    def test_coverage_honors_an_explicit_empty_mandatory_policy(self):
        result = CoverageCheck().check({
            'mandatory_specialists': [],
            'coverage': {'required': []},
            'specialist_results': [],
        })
        self.assertEqual(result['mandatory_specialists'], [])
        self.assertTrue(result['ready_for_lead_resolver'])


if __name__ == '__main__':
    unittest.main()
