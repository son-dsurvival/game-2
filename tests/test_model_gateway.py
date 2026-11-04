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


if __name__ == '__main__':
    unittest.main()
