import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'outside game'))
from admin_editor import AdminEditor
from approval import approve_proposal, bind_source_versions


def proposal(root, changes, identity='edit-one'):
    return approve_proposal(bind_source_versions({'status': 'proposal_ready', 'proposal_id': identity, 'changes': changes}, repo_root=root))


class EditorTests(unittest.TestCase):
    def test_audit_failure_rolls_back_and_retry_applies_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'markdown_files/notes.md'
            target.parent.mkdir()
            target.write_text('before', encoding='utf-8')
            approved = proposal(root, [{'target_file': 'markdown_files/notes.md', 'action': 'update', 'old_text': 'before', 'new_text': 'after'}])
            audit_file = root / 'outside game/audit/admin_operations.jsonl'
            audit_file.mkdir(parents=True)
            editor = AdminEditor(root)
            result = editor.apply(approved)
            self.assertEqual(result['status'], 'rejected')
            self.assertEqual(target.read_text(encoding='utf-8'), 'before')
            audit_file.rmdir()
            self.assertEqual(editor.apply(approved)['status'], 'applied')
            self.assertEqual(editor.apply(approved)['status'], 'applied')
            self.assertEqual(target.read_text(encoding='utf-8'), 'after')


if __name__ == '__main__':
    unittest.main()
