import tempfile
import unittest
from pathlib import Path

from backend.background_state import BackgroundStateStore


class BackgroundTests(unittest.TestCase):
    def test_even_visible_background_records_do_not_change_canon_without_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            register = root / 'markdown_files/Experimentation Register.md'
            register.parent.mkdir()
            register.write_text('Approved content only.', encoding='utf-8')
            store = BackgroundStateStore(register, private_state_path=root / 'brain/state/background_state.json')
            store.commit_tick({'tick_id': 'day-1-morning', 'position': {'day': 1, 'phase': 'Morning'}, 'world_updates': [{'description': 'An ally returned.', 'ooc_visibility': 'public', 'visibility': 'visible'}]})
            self.assertEqual(register.read_text(encoding='utf-8'), 'Approved content only.')
            self.assertEqual(store.load_ticks()[0]['world_updates'][0]['description'], 'An ally returned.')
