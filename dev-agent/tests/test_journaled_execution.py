import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from agent.worker_journal import WorkerJournal
from agent.journaled_execution import simulate_journaled_execution


class MockExecutor:
    swayz_test_double = True
    def __init__(self, result="passed", failure=False):
        self.result, self.failure = result, failure
        self.calls = 0
    def __call__(self, plan):
        self.calls += 1
        if self.failure:
            raise RuntimeError("simulated failure")
        return self.result


class JournaledExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "journal.db")
        journal = WorkerJournal(self.path)
        journal.record_admission("job1")
        journal.close()

    def state(self):
        journal = WorkerJournal(self.path)
        try:
            return journal.status("job1")[0]
        finally:
            journal.close()

    @patch("agent.journaled_execution.validate_reserved_signed_worker_plan")
    def test_success_transitions_admitted_running_passed(self, gate):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(executes=False))
        result = simulate_journaled_execution(
            job_id="job1", journal_path=self.path,
            mock_executor=MockExecutor(), **{"job_id": "job1"})
        self.assertEqual(result.state, "passed")
        self.assertFalse(result.docker_executed)
        self.assertEqual(self.state(), "passed")

    @patch("agent.journaled_execution.validate_reserved_signed_worker_plan")
    def test_gate_rejection_leaves_job_admitted(self, gate):
        gate.side_effect = PermissionError("stop engaged")
        runner = MockExecutor()
        with self.assertRaises(PermissionError):
            simulate_journaled_execution(job_id="job1", journal_path=self.path,
                mock_executor=runner, **{"job_id": "job1"})
        self.assertEqual(self.state(), "admitted")
        self.assertEqual(runner.calls, 0)

    @patch("agent.journaled_execution.validate_reserved_signed_worker_plan")
    def test_executor_failure_blocks_job(self, gate):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(executes=False))
        with self.assertRaises(RuntimeError):
            simulate_journaled_execution(job_id="job1", journal_path=self.path,
                mock_executor=MockExecutor(failure=True), **{"job_id": "job1"})
        self.assertEqual(self.state(), "blocked")

    @patch("agent.journaled_execution.validate_reserved_signed_worker_plan")
    def test_duplicate_job_cannot_execute_again(self, gate):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(executes=False))
        journal = WorkerJournal(self.path)
        journal.transition("job1", "admitted", "running")
        journal.transition("job1", "running", "passed")
        journal.close()
        runner = MockExecutor()
        with self.assertRaises(PermissionError):
            simulate_journaled_execution(job_id="job1", journal_path=self.path,
                mock_executor=runner, **{"job_id": "job1"})
        self.assertEqual(runner.calls, 0)

    @patch("agent.journaled_execution.validate_reserved_signed_worker_plan")
    def test_invalid_outcome_blocks_job(self, gate):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(executes=False))
        with self.assertRaises(ValueError):
            simulate_journaled_execution(job_id="job1", journal_path=self.path,
                mock_executor=MockExecutor("unexpected"), **{"job_id": "job1"})
        self.assertEqual(self.state(), "blocked")
