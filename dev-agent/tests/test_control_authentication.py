import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
from agent.control_authentication import ControlAuthenticator


class ControlAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "replay.db")
        self.key = b"k" * 32
        self.auth = ControlAuthenticator(self.path, self.key)

    def tearDown(self):
        self.auth.close()
        self.tmp.cleanup()

    def request(self, **changes):
        data = dict(action="status", job_id=None, nonce="a" * 32, timestamp=1000)
        data.update(changes)
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        sig = hmac.new(self.key, b"SWAYZ-CONTROL-V1\0" + raw, hashlib.sha256).hexdigest()
        return raw, sig

    def test_valid_request(self):
        self.assertEqual(self.auth.verify(*self.request(), now=1000)["action"], "status")

    def test_replay_rejected(self):
        self.auth.verify(*self.request(), now=1000)
        with self.assertRaises(PermissionError):
            self.auth.verify(*self.request(), now=1000)

    def test_replay_persists_restart(self):
        self.auth.verify(*self.request(), now=1000)
        self.auth.close()
        self.auth = ControlAuthenticator(self.path, self.key)
        with self.assertRaises(PermissionError):
            self.auth.verify(*self.request(), now=1000)

    def test_wrong_signature(self):
        raw, sig = self.request()
        with self.assertRaises(PermissionError):
            self.auth.verify(raw, "0" * 64, now=1000)

    def test_stale_timestamp(self):
        with self.assertRaises(PermissionError):
            self.auth.verify(*self.request(), now=1200)

    def test_unsupported_action(self):
        with self.assertRaises(PermissionError):
            self.auth.verify(*self.request(action="enable"), now=1000)

    def test_invalid_job_id(self):
        with self.assertRaises(ValueError):
            self.auth.verify(*self.request(action="job_status", job_id="../escape"), now=1000)

    def test_valid_job_status(self):
        self.assertEqual(self.auth.verify(*self.request(action="job_status", job_id="job_1"), now=1000)["job_id"], "job_1")
