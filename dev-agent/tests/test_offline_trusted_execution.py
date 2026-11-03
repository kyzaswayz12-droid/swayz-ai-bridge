"""Offline orchestration contract tests: no Docker, network or paid calls."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agent.offline_trusted_execution import simulate_trusted_execution


class MockExecutor:
    swayz_test_double = True
    def __init__(self, outcome="passed"):
        self.outcome = outcome
        self.calls = []
    def __call__(self, plan):
        self.calls.append(plan)
        return self.outcome


class OfflineTrustedExecutionTests(unittest.TestCase):
    @patch("agent.offline_trusted_execution.validate_reserved_signed_worker_plan")
    def test_all_gates_before_mock_execution(self, validate):
        plan = object()
        validate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(executes=False))
        runner = MockExecutor()
        result = simulate_trusted_execution(mock_executor=runner, job_id="job1")
        self.assertEqual(result.state, "passed")
        self.assertFalse(result.docker_executed)
        self.assertEqual(len(runner.calls), 1)
        validate.assert_called_once_with(job_id="job1")

    @patch("agent.offline_trusted_execution.validate_reserved_signed_worker_plan")
    def test_gate_failure_never_calls_runner(self, validate):
        validate.side_effect = PermissionError("Emergency stop engaged")
        runner = MockExecutor()
        with self.assertRaises(PermissionError):
            simulate_trusted_execution(mock_executor=runner, job_id="job1")
        self.assertEqual(runner.calls, [])

    @patch("agent.offline_trusted_execution.validate_reserved_signed_worker_plan")
    def test_arbitrary_callable_rejected(self, validate):
        with self.assertRaises(PermissionError):
            simulate_trusted_execution(mock_executor=lambda _: "passed", job_id="job1")
        validate.assert_not_called()

    @patch("agent.offline_trusted_execution.validate_reserved_signed_worker_plan")
    def test_missing_executor_rejected(self, validate):
        with self.assertRaises(PermissionError):
            simulate_trusted_execution(job_id="job1")
        validate.assert_not_called()

    @patch("agent.offline_trusted_execution.validate_reserved_signed_worker_plan")
    def test_invalid_mock_result_rejected(self, validate):
        validate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(executes=False))
        with self.assertRaises(PermissionError):
            simulate_trusted_execution(mock_executor=MockExecutor("unexpected"), job_id="job1")

    @patch("agent.offline_trusted_execution.validate_reserved_signed_worker_plan")
    def test_executable_plan_rejected(self, validate):
        validate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(executes=True))
        runner = MockExecutor()
        with self.assertRaises(PermissionError):
            simulate_trusted_execution(mock_executor=runner, job_id="job1")
        self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()
