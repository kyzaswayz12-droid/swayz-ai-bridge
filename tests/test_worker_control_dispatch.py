import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from app.core import Store, Reply, Ignore
from app.worker_control_dispatch import dispatch_bridge_control


class WorkerControlDispatchTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(allowed_channel="C1", allowed_users={"U1"})
        self.store = Store()
        self.client = Mock()
        self.payload = {"type": "event_callback", "event": {
            "type": "message", "user": "U1", "channel": "C1",
            "ts": "123.1", "text": "swayz status"}}

    def tearDown(self):
        self.store.close()

    def dispatch(self):
        return dispatch_bridge_control(self.payload, self.settings, self.store,
                                       1000, remote_client=self.client)

    def test_status_confirmed(self):
        self.client.request.return_value = {"action": "status", "stopped": True}
        self.assertIn("STOPPED", self.dispatch().text)

    def test_stop_confirmed(self):
        self.payload["event"]["text"] = "swayz stop"
        self.client.request.return_value = {"action": "stop", "stopped": True}
        self.assertIn("stop confirmed", self.dispatch().text)

    def test_stop_not_confirmed(self):
        self.payload["event"]["text"] = "swayz stop"
        self.client.request.return_value = {"action": "stop", "stopped": False}
        self.assertIn("NOT confirmed", self.dispatch().text)

    def test_network_error_not_confirmed(self):
        self.client.request.side_effect = TimeoutError()
        self.assertIn("NOT confirmed", self.dispatch().text)

    def test_unauthorised_user_no_call(self):
        self.payload["event"]["user"] = "U2"
        self.assertIsInstance(self.dispatch(), Ignore)
        self.client.request.assert_not_called()

    def test_duplicate_event_no_second_call(self):
        self.client.request.return_value = {"action": "status", "stopped": True}
        self.dispatch()
        self.assertIsInstance(self.dispatch(), Ignore)
        self.assertEqual(self.client.request.call_count, 1)

    def test_disconnected_mode(self):
        self.assertIn("not connected", dispatch_bridge_control(
            self.payload, self.settings, self.store, 1000).text)
