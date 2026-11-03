import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agent.execution_readiness import review_execution_readiness, execute_reviewed_plan


class ExecutionReadinessTests(unittest.TestCase):
    @patch("agent.execution_readiness.validate_reserved_signed_worker_plan")
    def test_valid_offline_plan(self, gate):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(
            executes=False, name="swayz-test-job1"))
        result = review_execution_readiness(expected_job_id="job1", job_id="job1")
        self.assertTrue(result.ready_for_supervised_review)
        self.assertFalse(result.docker_executed)

    @patch("agent.execution_readiness.validate_reserved_signed_worker_plan")
    def test_identity_mismatch_blocks_before_gate(self, gate):
        with self.assertRaises(PermissionError):
            review_execution_readiness(expected_job_id="job1", job_id="job2")
        gate.assert_not_called()

    @patch("agent.execution_readiness.validate_reserved_signed_worker_plan")
    def test_unsafe_plan_rejected(self, gate):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(
            executes=True, name="swayz-test-job1"))
        with self.assertRaises(PermissionError):
            review_execution_readiness(expected_job_id="job1", job_id="job1")

    @patch("agent.execution_readiness.validate_reserved_signed_worker_plan")
    def test_gate_failure_propagates(self, gate):
        gate.side_effect = PermissionError("Stop engaged")
        with self.assertRaises(PermissionError):
            review_execution_readiness(expected_job_id="job1", job_id="job1")

    def test_production_execution_disabled(self):
        with self.assertRaises(PermissionError):
            execute_reviewed_plan()
