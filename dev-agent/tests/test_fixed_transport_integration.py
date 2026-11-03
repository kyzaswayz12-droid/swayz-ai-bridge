"""Integration of fixed Docker transport with supervised cleanup adapter.

All process calls are patched; no Docker daemon is accessed.
"""
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent.worker_lifecycle import plan_worker_lifecycle
from agent.fixed_docker_transport import FixedDockerTransport
from agent.supervised_lifecycle_adapter import run_supervised_lifecycle

DIGEST = "sha256:" + "a" * 64


class FixedTransportIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        workspace = Path(self.temp.name) / "job1"
        workspace.mkdir()
        self.plan = plan_worker_lifecycle("job1", DIGEST, workspace=str(workspace))
        self.transport = FixedDockerTransport(self.plan)

    @patch("agent.fixed_docker_transport.subprocess.run")
    def test_supervised_success_with_verified_cleanup(self, run):
        def response(argv, **kwargs):
            if argv[1] == "run":
                return SimpleNamespace(returncode=0, stdout="OK", stderr="")
            if argv[1] == "kill":
                return SimpleNamespace(returncode=1, stdout="", stderr="not running")
            if argv[1] == "inspect":
                return SimpleNamespace(returncode=1, stdout="",
                    stderr="Error: No such object: swayz-test-job1")
            if argv[1] == "info":
                return SimpleNamespace(returncode=0, stdout="28.0", stderr="")
            raise AssertionError("Unexpected command")
        run.side_effect = response
        outcome = run_supervised_lifecycle(
            self.plan, transport=self.transport,
            daemon_probe=self.transport.daemon_healthy)
        self.assertEqual(outcome.state, "passed")
        self.assertTrue(outcome.cleanup_verified)
        self.assertEqual([call.args[0][1] for call in run.call_args_list],
                         ["run", "kill", "inspect", "info"])

    @patch("agent.fixed_docker_transport.subprocess.run")
    def test_daemon_failure_blocks_success(self, run):
        def response(argv, **kwargs):
            if argv[1] == "inspect":
                return SimpleNamespace(returncode=1, stdout="",
                    stderr="Error: No such object: swayz-test-job1")
            if argv[1] == "info":
                return SimpleNamespace(returncode=1, stdout="", stderr="unavailable")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        run.side_effect = response
        outcome = run_supervised_lifecycle(
            self.plan, transport=self.transport,
            daemon_probe=self.transport.daemon_healthy)
        self.assertEqual(outcome.state, "cleanup_unverified")
