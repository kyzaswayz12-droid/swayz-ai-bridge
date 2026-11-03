"""Final handoff gate tests. No Docker, network or paid APIs."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agent.final_dispatch_gate import revalidate_before_handoff


class FinalDispatchGateTests(unittest.TestCase):
    @patch("agent.final_dispatch_gate.validate_reserved_signed_worker_plan")
    def test_valid_handoff_is_not_execution(self, gate):
        gate.return_value = SimpleNamespace(
            lifecycle=SimpleNamespace(executes=False, name="swayz-test-job1"))
        decision = revalidate_before_handoff(job_id="job1")
        self.assertTrue(decision.ready_for_supervised_handoff)
        self.assertFalse(decision.docker_executed)
        gate.assert_called_once_with(job_id="job1")

    @patch("agent.final_dispatch_gate.validate_reserved_signed_worker_plan")
    def test_stop_failure_blocks_handoff(self, gate):
        gate.side_effect = PermissionError("Stop engaged")
        with self.assertRaises(PermissionError):
            revalidate_before_handoff(job_id="job1")

    @patch("agent.final_dispatch_gate.validate_reserved_signed_worker_plan")
    def test_mismatched_plan_blocks_handoff(self, gate):
        gate.return_value = SimpleNamespace(
            lifecycle=SimpleNamespace(executes=False, name="swayz-test-other"))
        with self.assertRaises(PermissionError):
            revalidate_before_handoff(job_id="job1")

    @patch("agent.final_dispatch_gate.validate_reserved_signed_worker_plan")
    def test_duplicate_identity_rejected(self, gate):
        with self.assertRaises(TypeError):
            revalidate_before_handoff(job_id="job1", **{"job_id": "other"})
        gate.assert_not_called()
