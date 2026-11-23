import tempfile
import unittest
from pathlib import Path

from brain.state.build_evidence_index import build_index, description_targets
from brain.state.evidence_ids import ensure_ids


class EvidenceIdTests(unittest.TestCase):
    def test_ids_are_inserted_once_and_survive_rename_and_move(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'markdown_files'
            source.mkdir()
            path = source / 'rules.md'
            path.write_text('## Alpha\n\nText.\n\n### Child\n\nMore.\n', encoding='utf-8')
            changed = ensure_ids(source)
            self.assertEqual(changed, [path.resolve()])
            first = path.read_text(encoding='utf-8')
            self.assertEqual(len(ensure_ids(source)), 0)
            ids = [line for line in first.splitlines() if 'evidence-id:' in line]
            self.assertEqual(len(ids), 2)

            path.write_text(
                first.replace('## Alpha', '## Renamed').replace('### Child', '### Moved Child'),
                encoding='utf-8',
            )
            self.assertEqual(len(ensure_ids(source)), 0)
            second = path.read_text(encoding='utf-8')
            self.assertEqual(ids, [line for line in second.splitlines() if 'evidence-id:' in line])

    def test_description_targets_include_new_or_renamed_sections_not_moves(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'markdown_files'
            source.mkdir()
            path = source / 'rules.md'
            path.write_text('## Alpha\n<!-- evidence-id: rules.alpha -->\nText.\n', encoding='utf-8')
            previous = build_index(source)
            path.write_text(
                '## Renamed\n<!-- evidence-id: rules.alpha -->\nText.\n\n## New\n<!-- evidence-id: rules.new -->\nText.\n',
                encoding='utf-8',
            )
            current = build_index(source, previous_index=previous)
            self.assertEqual(description_targets(previous, current), ['rules.alpha', 'rules.new'])


if __name__ == '__main__':
    unittest.main()
