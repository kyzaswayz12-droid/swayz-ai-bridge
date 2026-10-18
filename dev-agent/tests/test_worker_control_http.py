import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from agent.worker_control_http import create_control_app
from agent.worker_control_service import WorkerControlService


class WorkerControlHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.key = b"h" * 32
        self.service = WorkerControlService(str(root / "replay.db"),
                                            str(root / "stop.db"),
                                            str(root / "journal.db"), self.key)
        self.client = TestClient(create_control_app(self.service))

    def tearDown(self):
        self.client.close()
        self.service.close()
        self.tmp.cleanup()

    def request(self, action="status", job_id=None, nonce="a" * 32, timestamp=1000):
        import time
        data = dict(action=action, job_id=job_id, nonce=nonce,
                    timestamp=int(time.time()) if timestamp is None else timestamp)
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        sig = hmac.new(self.key, b"SWAYZ-CONTROL-V1\0" + raw, hashlib.sha256).hexdigest()
        return self.client.post("/control", content=raw,
                                headers={"content-type": "application/json",
                                         "x-swayz-signature": sig})

    def test_authenticated_status(self):
        response = self.request(timestamp=None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["stopped"])

    def test_stop_is_persistent(self):
        self.service.stop.enable(owner_authorised=True)
        response = self.request("stop", timestamp=None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.service.stop.is_stopped())

    def test_replay_rejected(self):
        self.assertEqual(self.request(timestamp=None).status_code, 200)
        self.assertEqual(self.request(timestamp=None).status_code, 403)

    def test_invalid_signature(self):
        response = self.client.post("/control", content=b"{}",
                                    headers={"content-type": "application/json",
                                             "x-swayz-signature": "0" * 64})
        self.assertEqual(response.status_code, 403)

    def test_oversize_rejected(self):
        response = self.client.post("/control", content=b"x" * 1025,
                                    headers={"content-type": "application/json"})
        self.assertEqual(response.status_code, 413)

    def test_wrong_content_type(self):
        response = self.client.post("/control", content=b"{}",
                                    headers={"content-type": "text/plain"})
        self.assertEqual(response.status_code, 415)

    def test_no_enable_endpoint(self):
        response = self.request("enable", timestamp=None)
        self.assertEqual(response.status_code, 403)

    def test_job_not_found(self):
        response = self.request("job_status", "job-1", timestamp=None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "not_found")

    def test_docs_disabled(self):
        self.assertEqual(self.client.get("/docs").status_code, 404)
