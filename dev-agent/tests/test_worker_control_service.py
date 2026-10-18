import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
from agent.worker_control_service import WorkerControlService


class WorkerControlServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.key = b"s" * 32
        self.args = (str(root / "replay.db"), str(root / "stop.db"),
                     str(root / "journal.db"), self.key)
        self.service = WorkerControlService(*self.args)

    def tearDown(self):
        self.service.close()
        self.tmp.cleanup()

    def request(self, action="status", job_id=None, nonce="a" * 32):
        data = dict(action=action, job_id=job_id, nonce=nonce, timestamp=1000)
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        sig = hmac.new(self.key, b"SWAYZ-CONTROL-V1\0" + raw, hashlib.sha256).hexdigest()
        return raw, sig

    def test_default_stopped(self):
        self.assertTrue(self.service.handle(*self.request(), now=1000)["stopped"])

    def test_stop_persists_restart(self):
        self.service.stop.enable(owner_authorised=True)
        self.assertFalse(self.service.stop.is_stopped())
        self.service.handle(*self.request("stop"), now=1000)
        self.service.close()
        self.service = WorkerControlService(*self.args)
        self.assertTrue(self.service.stop.is_stopped())

    def test_job_not_found(self):
        result = self.service.handle(*self.request("job_status", "job1"), now=1000)
        self.assertEqual(result["state"], "not_found")

    def test_job_state(self):
        self.service.journal.record_admission("job1")
        result = self.service.handle(*self.request("job_status", "job1"), now=1000)
        self.assertEqual(result["state"], "admitted")

    def test_no_enable_command(self):
        with self.assertRaises(PermissionError):
            self.service.handle(*self.request("enable"), now=1000)

    def test_replay_rejected(self):
        self.service.handle(*self.request(), now=1000)
        with self.assertRaises(PermissionError):
            self.service.handle(*self.request(), now=1000)
