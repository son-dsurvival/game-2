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

    def test_append_only_journal_survives_snapshot_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RuntimeStateStore(directory)
            store.save({'campaign_id': 'campaign-one', 'play_gate': 'open'})
            store.append_event('operation_started', operation_id='turn-one', original_input='I wait.')
            store.save({'play_gate': 'retry'})
            store.append_event('stage_failed', operation_id='turn-one', stage='lead_resolver_decision')
            events = store.journal_events(operation_id='turn-one')
            self.assertEqual([item['event'] for item in events], ['operation_started', 'stage_failed'])
            self.assertEqual(store.load()['play_gate'], 'retry')


if __name__ == '__main__':
    unittest.main()
