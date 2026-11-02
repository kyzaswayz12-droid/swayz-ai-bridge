import unittest
from app.control import handle_control_event
from app.core import Settings, Store, Reply, Ignore


class BridgeControlRoutingTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.settings = Settings("C1", frozenset({"U1"}), 0, 0)

    def tearDown(self):
        self.store.close()

    def call(self, text, *, user="U1", channel="C1", ts="1"):
        payload = {"type": "event_callback", "event": {
            "type": "message", "text": text, "user": user,
            "channel": channel, "ts": ts}}
        return handle_control_event(payload, self.settings, self.store, 1000)

    def test_status_is_explicitly_disconnected(self):
        result = self.call("swayz status")
        self.assertIsInstance(result, Reply)
        self.assertIn("not connected", result.text)

    def test_stop_does_not_claim_success(self):
        result = self.call("swayz stop")
        self.assertIn("NOT executed", result.text)

    def test_unauthorised_user(self):
        self.assertIsInstance(self.call("swayz status", user="U2"), Ignore)

    def test_unauthorised_channel(self):
        self.assertIsInstance(self.call("swayz status", channel="C2"), Ignore)

    def test_replay(self):
        self.call("swayz status")
        self.assertIsInstance(self.call("swayz status"), Ignore)
