import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'outside game'))
from admin_agent import AdminAgent  # noqa: E402
from brain.runtime_commands import (
    ADMIN_AGENT_COMMANDS,
    LEAD_RESOLVER_COMMANDS,
    normalize_agent_command,
)


class AgentCommandTests(unittest.TestCase):
    def test_admin_can_request_safe_commands_but_not_protected_commands(self):
        self.assertEqual(
            normalize_agent_command({'name': 'status'}, allowed=ADMIN_AGENT_COMMANDS),
            {'name': '/status', 'argument': ''},
        )
        for name in ('/new-game', '/cancel-setup', '/approve', '/main', '/quit'):
            with self.assertRaises(ValueError):
                normalize_agent_command({'name': name}, allowed=ADMIN_AGENT_COMMANDS)

    def test_admin_response_preserves_a_valid_command(self):
        result = AdminAgent._validate({
            'status': 'answered', 'answer': 'I will show the current stage.',
            'diagnosis': {'issue': 'status requested', 'why': 'status is available'},
            'runtime_command': {'name': '/status'},
        }, 'admin-test')
        self.assertEqual(result['runtime_command'], {'name': '/status', 'argument': ''})

    def test_lead_can_request_only_end_day(self):
        self.assertEqual(
            normalize_agent_command({'name': '/end-day'}, allowed=LEAD_RESOLVER_COMMANDS),
            {'name': '/end-day', 'argument': ''},
        )
        with self.assertRaises(ValueError):
            normalize_agent_command({'name': '/status'}, allowed=LEAD_RESOLVER_COMMANDS)


if __name__ == '__main__':
    unittest.main()
