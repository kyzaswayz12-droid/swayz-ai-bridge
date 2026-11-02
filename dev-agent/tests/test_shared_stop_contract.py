"""Offline shared-stop contract: control API and dispatch gate share state.

These tests do not enable autonomy, call providers, or run Docker.
"""
import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
from agent.worker_control_service import WorkerControlService
from agent.emergency_stop import EmergencyStop


class SharedStopContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.stop_path = str(root / "shared-stop.db")
        self.service = WorkerControlService(
            str(root / "replay.db"), self.stop_path,
            str(root / "journal.db"), b"k" * 32)

    def tearDown(self):
        self.service.close()
        self.tmp.cleanup()

    def signed_stop(self):
        import time
        data = {"action": "stop", "job_id": None,
                "nonce": "a" * 32, "timestamp": int(time.time())}
        raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        sig = hmac.new(b"k" * 32, b"SWAYZ-CONTROL-V1\0" + raw, hashlib.sha256).hexdigest()
        return raw, sig

    def test_control_stop_blocks_same_database_dispatch_gate(self):
        gate = EmergencyStop(self.stop_path)
        try:
            gate.enable(owner_authorised=True)
            gate.require_running()
            response = self.service.handle(*self.signed_stop())
            self.assertTrue(response["stopped"])
            with self.assertRaises(PermissionError):
                gate.require_running()
        finally:
            gate.close()

    def test_stop_survives_control_service_restart(self):
        self.service.handle(*self.signed_stop())
        self.service.close()
        root = Path(self.stop_path).parent
        self.service = WorkerControlService(
            str(root / "replay.db"), self.stop_path,
            str(root / "journal.db"), b"k" * 32)
        gate = EmergencyStop(self.stop_path)
        try:
            with self.assertRaises(PermissionError):
                gate.require_running()
        finally:
            gate.close()
