import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from agent.slack_remote_control import route_verified_remote_control
from agent.slack_verified_controls import Ignore, Reply


class RemoteSlackControlTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(allowed_users={"U1"}, allowed_channel="C1")
        self.store = Mock()
        self.store.claim_message.return_value = True
        self.client = Mock()
        self.payload = {"type": "event_callback", "event": {
            "type": "message", "user": "U1", "channel": "C1",
            "ts": "123.456", "text": "swayz status"}}

    def call(self):
        return route_verified_remote_control(self.payload, self.settings,
                                             self.store, 1000, client=self.client)

    def test_status(self):
        self.client.request.return_value = {"action": "status", "stopped": True}
        self.assertIn("STOPPED", self.call().text)

    def test_stop_requires_confirmation(self):
        self.payload["event"]["text"] = "swayz stop"
        self.client.request.return_value = {"action": "stop", "stopped": False}
        self.assertIn("NOT confirmed", self.call().text)

    def test_stop_success(self):
        self.payload["event"]["text"] = "swayz stop"
        self.client.request.return_value = {"action": "stop", "stopped": True}
        self.assertIn("confirmed", self.call().text)

    def test_network_failure_not_success(self):
        self.client.request.side_effect = TimeoutError()
        self.assertIn("NOT confirmed", self.call().text)

    def test_unauthorised_user_no_call(self):
        self.payload["event"]["user"] = "OTHER"
        self.assertIsInstance(self.call(), Ignore)
        self.client.request.assert_not_called()

    def test_duplicate_no_call(self):
        self.store.claim_message.return_value = False
        self.assertIsInstance(self.call(), Ignore)
        self.client.request.assert_not_called()
