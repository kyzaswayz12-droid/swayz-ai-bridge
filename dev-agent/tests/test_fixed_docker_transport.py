"""Restricted transport tests; all subprocess calls mocked."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent.worker_lifecycle import plan_worker_lifecycle
from agent.fixed_docker_transport import FixedDockerTransport

DIGEST = "sha256:" + "a" * 64


class FixedDockerTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "job1"
        self.workspace.mkdir()
        self.plan = plan_worker_lifecycle("job1", DIGEST, workspace=str(self.workspace))
        self.transport = FixedDockerTransport(self.plan, require_running=lambda: None)

    @patch("agent.fixed_docker_transport.subprocess.run")
    def test_fixed_run_command_accepted(self, run):
        run.return_value = SimpleNamespace(returncode=0)
        result = self.transport(list(self.plan.run_argv),
            capture_output=True, text=True, timeout=120, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(run.call_count, 1)

    @patch("agent.fixed_docker_transport.subprocess.run")
    def test_arbitrary_command_refused(self, run):
        with self.assertRaises(PermissionError):
            self.transport(["docker", "ps"], capture_output=True,
                           text=True, timeout=5, check=False)
        run.assert_not_called()

    @patch("agent.fixed_docker_transport.subprocess.run")
    def test_long_timeout_refused(self, run):
        with self.assertRaises(PermissionError):
            self.transport(list(self.plan.run_argv), capture_output=True,
                           text=True, timeout=600, check=False)
        run.assert_not_called()

    @patch("agent.fixed_docker_transport.subprocess.run")
    def test_daemon_probe_checks_success(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout="28.0\n")
        self.assertTrue(self.transport.daemon_healthy())

    @patch("agent.fixed_docker_transport.subprocess.run")
    def test_daemon_probe_fails_closed(self, run):
        run.side_effect = subprocess.TimeoutExpired(["docker", "info"], 5)
        self.assertFalse(self.transport.daemon_healthy())

    def test_plan_without_workspace_rejected(self):
        plan = plan_worker_lifecycle("job1", DIGEST)
        with self.assertRaises(PermissionError):
            FixedDockerTransport(plan, require_running=lambda: None)
