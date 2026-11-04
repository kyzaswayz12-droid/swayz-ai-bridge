"""Tests that the mock-only worker service rejects production dependencies."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent.local_supervised_worker_service import run_local_supervised_worker


class WorkerServiceDefaultDenyTests(unittest.TestCase):
    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_default_real_dependencies_rejected_before_validation(self, gate):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PermissionError):
                run_local_supervised_worker(
                    job_id="job1", journal_path=str(Path(d) / "journal.db"),
                    server_control_db=str(Path(d) / "stop.db"))
        gate.assert_not_called()

    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_unmarked_executor_rejected_before_validation(self, gate):
        def factory(plan, **kwargs):
            return object()
        def runner(plan, **kwargs):
            return object()
        factory.swayz_test_double = True
        with self.assertRaises(PermissionError):
            run_local_supervised_worker(
                job_id="job1", journal_path="/missing/journal.db",
                server_control_db="/missing/stop.db",
                transport_factory=factory, lifecycle_runner=runner)
        gate.assert_not_called()
