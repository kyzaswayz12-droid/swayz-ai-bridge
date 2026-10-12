import subprocess
import unittest
from types import SimpleNamespace
from agent.worker_lifecycle import plan_worker_lifecycle
from agent.worker_runner import run_worker_plan

DIGEST = "sha256:" + "a" * 64


class WorkerRunnerTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_worker_lifecycle("job1", DIGEST)

    def test_disabled_rejects(self):
        with self.assertRaises(PermissionError):
            run_worker_plan(self.plan)

    def test_real_runner_refused(self):
        with self.assertRaises(PermissionError):
            run_worker_plan(self.plan, enabled=True)

    def test_mock_success(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout="OK", stderr="")
        result = run_worker_plan(self.plan, enabled=True, runner=runner)
        self.assertEqual(result.status, "passed")
        self.assertEqual(len(calls), 1)

    def test_timeout_cleanup_verified(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            if len(calls) == 1:
                raise subprocess.TimeoutExpired(argv, 120)
            return SimpleNamespace(returncode=0 if len(calls) == 2 else 1,
                                   stdout="", stderr="")
        result = run_worker_plan(self.plan, enabled=True, runner=runner)
        self.assertEqual(result.status, "timed_out")
        self.assertTrue(result.cleanup_verified)
        self.assertEqual(len(calls), 3)

    def test_timeout_cleanup_failure_blocks(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            if len(calls) == 1:
                raise subprocess.TimeoutExpired(argv, 120)
            raise OSError("Docker unavailable")
        result = run_worker_plan(self.plan, enabled=True, runner=runner)
        self.assertEqual(result.status, "cleanup_unverified")
        self.assertFalse(result.cleanup_verified)
