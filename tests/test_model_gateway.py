import json
import tempfile
import unittest

from brain.model_gateway import ModelGateway


class ModelGatewayTests(unittest.TestCase):
    def test_campaign_and_state_versions_prevent_stale_reuse(self):
        with tempfile.TemporaryDirectory() as root:
            answers = iter(['first', 'second'])
            gateway = ModelGateway(root, transport=lambda request: next(answers))
            args = dict(stage='rules', messages=[{'role': 'user', 'content': 'same question'}])
            gateway.complete(**args, metadata={'campaign_id': 'one', 'state_version': 1})
            result = gateway.complete(**args, metadata={'campaign_id': 'two', 'state_version': 1})
            self.assertEqual(result.content, 'second')
            self.assertFalse(result.reused)

    def test_malformed_json_is_recorded_but_never_reused(self):
        with tempfile.TemporaryDirectory() as root:
            answers = iter(['{broken', '{}'])
            gateway = ModelGateway(root, transport=lambda request: next(answers))
            args = dict(stage='rules', messages=[{'role': 'user', 'content': 'answer JSON'}], json_mode=True)
            self.assertEqual(gateway.complete(**args).content, '{broken')
            result = gateway.complete(**args)
            self.assertEqual(result.content, '{}')
            self.assertFalse(result.reused)

    def test_volatile_turn_metadata_does_not_defeat_exact_reuse(self):
        with tempfile.TemporaryDirectory() as root:
            answers = iter(['one'])
            gateway = ModelGateway(root, transport=lambda request: next(answers))
            args = dict(stage='rules', messages=[{'role': 'user', 'content': 'same question'}])
            gateway.complete(**args, metadata={
                'campaign_id': 'one', 'state_version': 3, 'turn_id': 'turn-a',
                'revision': 1,
            })
            result = gateway.complete(**args, metadata={
                'campaign_id': 'one', 'state_version': 3, 'turn_id': 'turn-b',
                'revision': 2,
            })
            self.assertTrue(result.reused)
            self.assertEqual(result.content, 'one')

    def test_legacy_invalidation_tombstones_do_not_destroy_valid_cache(self):
        with tempfile.TemporaryDirectory() as root:
            answers = iter(['one'])
            gateway = ModelGateway(root, transport=lambda request: next(answers))
            args = dict(stage='rules', messages=[{'role': 'user', 'content': 'same question'}])
            first = gateway.complete(**args)
            with open(gateway.journal_path, 'a', encoding='utf-8') as handle:
                handle.write(json.dumps({'status': 'invalidated', 'cache_key': first.cache_key}) + '\n')
            result = gateway.complete(**args)
            self.assertTrue(result.reused)
            self.assertEqual(result.content, 'one')


if __name__ == '__main__':
    unittest.main()
