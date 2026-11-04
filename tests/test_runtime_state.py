import tempfile
import unittest
from pathlib import Path

from brain.runtime_state import RuntimeStateStore


class RuntimeStateTests(unittest.TestCase):
    def test_restart_preserves_operation_checkpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RuntimeStateStore(directory)
            store.save({'campaign_id': 'campaign-one', 'operation': {'id': 'turn-one', 'stage': 'narrate', 'result': {'status': 'resolved'}}})
            resumed = RuntimeStateStore(directory).load()
            self.assertEqual(resumed['operation']['stage'], 'narrate')
            self.assertEqual(resumed['campaign_id'], 'campaign-one')


if __name__ == '__main__':
    unittest.main()
