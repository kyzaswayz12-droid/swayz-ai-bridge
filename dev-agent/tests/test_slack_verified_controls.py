import unittest
from dataclasses import dataclass
from agent.slack_verified_controls import Reply, Ignore


@dataclass(frozen=True)
class Settings:
    allowed_channel: str
    allowed_users: frozenset
    per_user_limit: int
    total_limit: int


class Store:
    def __init__(self):
        self.seen = set()
    def claim_message(self, channel, ts, now):
        key = (channel, ts)
        if key in self.seen:
            return False
        self.seen.add(key)
        return True
    def close(self):
        pass
from agent.emergency_stop import EmergencyStop
from agent.slack_verified_controls import handle_verified_control_event


class FakeJournal:
    def status(self, job_id):
        return ("passed", 0, "") if job_id == "job1" else None


class SlackVerifiedControlsTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings("C1", frozenset({"U1"}), 0, 0)
        self.store = Store()
        self.stop = EmergencyStop(":memory:")
        self.journal = FakeJournal()

    def tearDown(self):
        self.stop.close()
        self.store.close()

    def handle(self, text, user="U1", channel="C1", ts="1"):
        payload = {"type": "event_callback", "event": {
            "type": "message", "user": user, "channel": channel,
            "ts": ts, "text": text}}
        return handle_verified_control_event(
            payload, self.settings, self.store, 1000,
            emergency_stop=self.stop, journal=self.journal)

    def test_status_is_available_when_model_calls_disabled(self):
        result = self.handle("swayz status")
        self.assertIsInstance(result, Reply)
        self.assertIn("STOPPED", result.text)

    def test_stop_is_idempotent(self):
        self.stop.enable(owner_authorised=True)
        result = self.handle("swayz stop")
        self.assertIsInstance(result, Reply)
        self.assertTrue(self.stop.is_stopped())

    def test_job_status(self):
        self.assertIn("passed", self.handle("swayz job job1").text)

    def test_unauthorised_user(self):
        self.assertIsInstance(self.handle("swayz stop", user="U2"), Ignore)

    def test_unauthorised_channel(self):
        self.assertIsInstance(self.handle("swayz stop", channel="C2"), Ignore)

    def test_replayed_message(self):
        self.handle("swayz status")
        self.assertIsInstance(self.handle("swayz stop"), Ignore)
