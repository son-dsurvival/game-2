import tempfile
import unittest
from brain.dice import DiceJournal


class DiceTests(unittest.TestCase):
    def test_saved_roll_survives_restart_and_rejects_changed_request(self):
        with tempfile.TemporaryDirectory() as root:
            dice = DiceJournal(root, random_below=lambda sides: 6)
            self.assertEqual(dice.roll('campaign/tick/action', sides=20)['result'], 7)
            restarted = DiceJournal(root, random_below=lambda sides: 19)
            self.assertEqual(restarted.roll('campaign/tick/action', sides=20)['result'], 7)
            with self.assertRaises(ValueError):
                restarted.roll('campaign/tick/action', sides=100)
