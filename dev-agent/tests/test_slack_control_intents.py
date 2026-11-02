import unittest
from agent.slack_control_intents import parse_slack_control


class SlackControlIntentTests(unittest.TestCase):
    def test_status(self):
        self.assertEqual(parse_slack_control("swayz status").action, "status")

    def test_stop(self):
        self.assertEqual(parse_slack_control("swayz stop").action, "stop")

    def test_job_status(self):
        result = parse_slack_control("swayz job job_123")
        self.assertEqual((result.action, result.job_id), ("job_status", "job_123"))

    def test_unknown_command_rejected(self):
        with self.assertRaises(ValueError):
            parse_slack_control("swayz deploy production")

    def test_invalid_job_id_rejected(self):
        with self.assertRaises(ValueError):
            parse_slack_control("swayz job ../escape")

    def test_unprefixed_command_rejected(self):
        with self.assertRaises(ValueError):
            parse_slack_control("stop")
