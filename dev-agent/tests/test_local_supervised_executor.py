"""Local supervised executor ordering and refusal tests; no Docker calls."""
import subprocess
import unittest
from unittest.mock import patch
from agent.worker_lifecycle import plan_worker_lifecycle
from agent.local_supervised_executor import execute_local_supervised_plan

DIGEST = "sha256:" + "a" * 64


class LocalSupervisedExecutorTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_worker_lifecycle("job1", DIGEST)

    def run_plan(self, **changes):
        args = dict(plan=self.plan, job_id="job1", image_digest=DIGEST,
                    snapshot=None, approved_image_digests=frozenset({DIGEST}),
                    require_running=lambda: None, run_command=lambda _: "mock-ok")
        args.update(changes)
        return execute_local_supervised_plan(**args)

    @patch("agent.local_supervised_executor.verify_fixed_worker_plan")
    def test_stop_checked_before_transport(self, verify):
        calls = []
        self.assertEqual(self.run_plan(
            require_running=lambda: calls.append("stop"),
            run_command=lambda _: calls.append("transport") or "mock-ok"), "mock-ok")
        self.assertEqual(calls, ["stop", "transport"])
        verify.assert_called_once()

    @patch("agent.local_supervised_executor.verify_fixed_worker_plan")
    def test_engaged_stop_never_invokes_transport(self, verify):
        calls = []
        def stopped():
            raise PermissionError("stop engaged")
        with self.assertRaises(PermissionError):
            self.run_plan(require_running=stopped,
                          run_command=lambda _: calls.append("executed"))
        self.assertEqual(calls, [])

    def test_direct_subprocess_refused(self):
        with self.assertRaises(PermissionError):
            self.run_plan(run_command=subprocess.run)

    def test_missing_stop_check_refused(self):
        with self.assertRaises(PermissionError):
            self.run_plan(require_running=None)

    def test_unapproved_image_rejected(self):
        with self.assertRaises(PermissionError):
            self.run_plan(approved_image_digests=frozenset())

    def test_mismatched_job_id_rejected(self):
        with self.assertRaises(PermissionError):
            self.run_plan(job_id="other")
