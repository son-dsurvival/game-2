import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'outside game'))
from admin_editor import AdminEditor
from approval import approve_proposal, bind_source_versions


def proposal(root, changes, identity='edit-one'):
    return approve_proposal(bind_source_versions({'status': 'proposal_ready', 'proposal_id': identity, 'proposed_by': 'admin_agent', 'changes': changes}, repo_root=root))


class EditorTests(unittest.TestCase):
    def test_rules_file_is_read_only_to_admin_editor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'markdown_files/game rules (1).md'
            target.parent.mkdir()
            target.write_text('original rules', encoding='utf-8')
            approved = proposal(root, [{
                'target_file': 'markdown_files/game rules (1).md',
                'action': 'update',
                'old_text': 'original rules',
                'new_text': 'changed rules',
            }], identity='rules-edit')
            result = AdminEditor(root).apply(approved)
            self.assertEqual(result['status'], 'rejected')
            self.assertEqual(target.read_text(encoding='utf-8'), 'original rules')

    def test_approved_technical_json_catalog_change_applies_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'brain/info/router_taxonomy/tags.json'
            target.parent.mkdir(parents=True)
            target.write_text('{"tags": {}}\n', encoding='utf-8')
            approved = proposal(root, [{
                'target_file': 'brain/info/router_taxonomy/tags.json',
                'action': 'update',
                'old_text': '{"tags": {}}\n',
                'new_text': '{\n  "tags": {"context.test": {}}\n}\n',
            }], identity='json-catalog')
            result = AdminEditor(root).apply(approved)
            self.assertEqual(result['status'], 'applied')
            self.assertIn('context.test', target.read_text(encoding='utf-8'))

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
