import unittest
from agent.worker_lifecycle import plan_worker_lifecycle

DIGEST = "sha256:" + "a" * 64


class WorkerLifecycleTests(unittest.TestCase):
    def test_fixed_offline_plan_and_cleanup_identity(self):
        plan = plan_worker_lifecycle("job1", DIGEST)
        self.assertEqual(plan.name, "swayz-test-job1")
        self.assertEqual(plan.kill_argv, ("docker", "kill", plan.name))
        self.assertIn("none", plan.run_argv)
        self.assertIn("--read-only", plan.run_argv)
        self.assertIn("--cap-drop", plan.run_argv)
        self.assertFalse(plan.executes)

    def test_invalid_job_id_rejected(self):
        with self.assertRaises(ValueError):
            plan_worker_lifecycle("../escape", DIGEST)

    def test_placeholder_digest_rejected(self):
        with self.assertRaises(ValueError):
            plan_worker_lifecycle("job1", "sha256:" + "0" * 64)

    def test_invalid_timeout_rejected(self):
        with self.assertRaises(ValueError):
            plan_worker_lifecycle("job1", DIGEST, timeout_seconds=0)
