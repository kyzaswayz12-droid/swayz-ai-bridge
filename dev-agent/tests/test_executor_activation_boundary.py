"""Activation boundary regression: untrusted queue cannot start executor.

Tests existing systemd adapter without systemd, Docker, signing keys or paid APIs.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.systemd_generated_job_adapter import run_prepared_generated_job


class ExecutorActivationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.snapshots = self.root / "snapshots"
        self.snapshots.mkdir()
        self.snapshot = self.snapshots / "job1"
        self.snapshot.mkdir()
        self.requests = self.root / "requests"
        self.requests.mkdir()
        self.systemctl_calls = []

    def invoke(self, **overrides):
        args = dict(job_id="job1", snapshot=str(self.snapshot),
                    snapshot_root=str(self.snapshots), expected_hashes={},
                    signing_key_path=str(self.root / "missing.key"),
                    require_running=lambda: None,
                    systemctl=lambda *a, **k: self.systemctl_calls.append(a))
        args.update(overrides)
        with patch("agent.systemd_generated_job_adapter.REQUESTS", self.requests), patch(
                "agent.systemd_generated_job_adapter.verify_snapshot_before_execution"):
            return run_prepared_generated_job(**args)

    def test_missing_signed_request_never_starts_executor(self):
        with self.assertRaises(PermissionError):
            self.invoke()
        self.assertEqual(self.systemctl_calls, [])

    def test_symlink_request_never_starts_executor(self):
        target = self.root / "other.json"
        target.write_text("{}")
        (self.requests / "job1.json").symlink_to(target)
        with self.assertRaises(PermissionError):
            self.invoke()
        self.assertEqual(self.systemctl_calls, [])

    def test_invalid_job_id_never_starts_executor(self):
        with self.assertRaises(ValueError):
            self.invoke(job_id="../job1")
        self.assertEqual(self.systemctl_calls, [])

    def test_missing_authoritative_stop_callback_never_starts_executor(self):
        with self.assertRaises(PermissionError):
            self.invoke(require_running=None)
        self.assertEqual(self.systemctl_calls, [])
