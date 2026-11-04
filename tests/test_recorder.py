import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brain.model_gateway import model_scope
from brain.recorder import SessionRecorder


class RecorderTests(unittest.TestCase):
    def test_recording_retry_is_idempotent_and_promoted_records_do_not_reappear(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'offline-test'}):
            root = Path(directory)
            memory = root / 'markdown_files/TEMP_MEMORY.md'
            memory.parent.mkdir()
            memory.write_text('# Session\n', encoding='utf-8')
            lead = {'turn_id': 'turn-one', 'position': {'day': 1, 'phase': 'Morning'}, 'status': 'resolved', 'resolution_record': {'status': 'resolved', 'outcome': 'A quiet morning.', 'time_changes': []}}
            with model_scope(root, {'campaign_id': 'test'}, lambda request: json.dumps({'summary': 'A quiet morning.', 'segments': []})):
                recorder = SessionRecorder(root)
                recorder.record(lead)
                retried = SessionRecorder(root).record(lead)
                self.assertEqual(retried['status'], 'already_recorded')
                self.assertEqual(len(recorder.pending_records(day=1)), 1)
                recorder.mark_promoted(['turn-one'])
                self.assertEqual(recorder.pending_records(day=1), [])


if __name__ == '__main__':
    unittest.main()
