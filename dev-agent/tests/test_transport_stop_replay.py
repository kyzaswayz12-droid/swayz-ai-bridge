"""One-shot Docker transport stop and replay checks (no Docker execution)."""
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from agent.worker_lifecycle import plan_worker_lifecycle
from agent.fixed_docker_transport import FixedDockerTransport


class TransportStopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = Path(self.tmp.name) / "job1"
        p.mkdir()
        self.plan = plan_worker_lifecycle("job1", "sha256:" + "a" * 64, workspace=str(p))

    def call(self, transport):
        return transport(list(self.plan.run_argv), capture_output=True,
                         text=True, timeout=120, check=False)

    def test_missing_stop_callback_rejected(self):
        with self.assertRaises(PermissionError):
            FixedDockerTransport(self.plan, require_running=None)

    @patch("agent.fixed_docker_transport.subprocess.run")
    def test_engaged_stop_rejects_before_subprocess(self, run):
        def stopped():
            raise PermissionError("Emergency stop engaged")
        transport = FixedDockerTransport(self.plan, require_running=stopped)
        with self.assertRaises(PermissionError):
            self.call(transport)
        run.assert_not_called()

    @patch("agent.fixed_docker_transport.subprocess.run")
    def test_one_shot_run_cannot_be_replayed(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")
        transport = FixedDockerTransport(self.plan, require_running=lambda: None)
        self.call(transport)
        with self.assertRaises(PermissionError):
            self.call(transport)
        self.assertEqual(run.call_count, 1)

    @patch("agent.fixed_docker_transport.subprocess.run")
    def test_cleanup_not_allowed_before_run(self, run):
        transport = FixedDockerTransport(self.plan, require_running=lambda: None)
        with self.assertRaises(PermissionError):
            transport(list(self.plan.kill_argv), capture_output=True,
                      text=True, timeout=10, check=False)
        run.assert_not_called()
