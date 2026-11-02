import subprocess
import unittest
from types import SimpleNamespace
from agent.worker_lifecycle import plan_worker_lifecycle
from agent.worker_runner import run_worker_plan


class DockerDaemonFailureTests(unittest.TestCase):
    def test_inspect_daemon_error_is_not_cleanup_success(self):
        plan = plan_worker_lifecycle("job1", "sha256:" + "a" * 64)
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            if len(calls) == 1:
                raise subprocess.TimeoutExpired(argv, 120)
            return SimpleNamespace(returncode=0 if len(calls) == 2 else 125,
                                   stdout="", stderr="daemon unavailable")
        result = run_worker_plan(plan, enabled=True, runner=runner)
        self.assertEqual(result.status, "cleanup_unverified")
        self.assertFalse(result.cleanup_verified)
