import subprocess
import unittest
from types import SimpleNamespace
from agent.worker_lifecycle import plan_worker_lifecycle
from agent.worker_runner import run_worker_plan

IMAGE = "sha256:" + "a" * 64


class WorkerCleanupVerificationTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_worker_lifecycle("job1", IMAGE)

    def simulate(self, kill_status, inspect_status):
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            if len(calls) == 1:
                raise subprocess.TimeoutExpired(argv, 120)
            return SimpleNamespace(returncode=kill_status if len(calls) == 2 else inspect_status,
                                   stdout="", stderr="")
        return run_worker_plan(self.plan, enabled=True, runner=runner)

    def test_successful_kill_and_absence_verified(self):
        result = self.simulate(0, 1)
        self.assertEqual(result.status, "timed_out")
        self.assertTrue(result.cleanup_verified)

    def test_failed_kill_not_considered_clean(self):
        result = self.simulate(1, 1)
        self.assertEqual(result.status, "cleanup_unverified")
        self.assertFalse(result.cleanup_verified)

    def test_container_still_present_blocks(self):
        result = self.simulate(0, 0)
        self.assertEqual(result.status, "cleanup_unverified")
        self.assertFalse(result.cleanup_verified)
