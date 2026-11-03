"""Supervised lifecycle adapter tests; never invokes Docker."""
import subprocess
import unittest
from types import SimpleNamespace
from agent.worker_lifecycle import plan_worker_lifecycle
from agent.supervised_lifecycle_adapter import run_supervised_lifecycle


class FakeTransport:
    def __init__(self, *, timeout=False, inspect_stderr=None):
        self.calls = []
        self.timeout = timeout
        self.inspect_stderr = inspect_stderr
    def __call__(self, argv, **kwargs):
        self.calls.append(tuple(argv))
        if argv[1] == "run":
            if self.timeout:
                raise subprocess.TimeoutExpired(argv, 1)
            return SimpleNamespace(returncode=0, stdout="OK", stderr="")
        if argv[1] == "kill":
            return SimpleNamespace(returncode=1, stdout="", stderr="not running")
        if argv[1] == "inspect":
            return SimpleNamespace(returncode=1, stdout="",
                stderr=self.inspect_stderr if self.inspect_stderr is not None
                else "Error: No such object: swayz-test-job1")
        raise AssertionError("Unexpected command")


class SupervisedLifecycleAdapterTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_worker_lifecycle("job1", "sha256:" + "a" * 64)

    def test_no_transport_rejected(self):
        with self.assertRaises(PermissionError):
            run_supervised_lifecycle(self.plan)

    def test_direct_subprocess_rejected(self):
        with self.assertRaises(PermissionError):
            run_supervised_lifecycle(self.plan, transport=subprocess.run,
                                     daemon_probe=lambda: True)

    def test_success_requires_verified_cleanup(self):
        transport = FakeTransport()
        result = run_supervised_lifecycle(self.plan, transport=transport,
                                          daemon_probe=lambda: True)
        self.assertEqual(result.state, "passed")
        self.assertTrue(result.cleanup_verified)
        self.assertEqual([c[1] for c in transport.calls], ["run", "kill", "inspect"])

    def test_daemon_unhealthy_blocks_success(self):
        result = run_supervised_lifecycle(self.plan, transport=FakeTransport(),
                                          daemon_probe=lambda: False)
        self.assertEqual(result.state, "cleanup_unverified")

    def test_generic_inspect_error_blocks_success(self):
        result = run_supervised_lifecycle(
            self.plan, transport=FakeTransport(inspect_stderr="daemon offline"),
            daemon_probe=lambda: True)
        self.assertEqual(result.state, "cleanup_unverified")

    def test_timeout_cleanup_verified(self):
        result = run_supervised_lifecycle(self.plan,
            transport=FakeTransport(timeout=True), daemon_probe=lambda: True)
        self.assertEqual(result.state, "timed_out")
        self.assertTrue(result.cleanup_verified)


if __name__ == "__main__":
    unittest.main()
