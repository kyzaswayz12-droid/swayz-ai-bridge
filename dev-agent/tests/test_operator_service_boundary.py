"""Operator-supervised production path tests; never contact Docker."""
import unittest
from unittest.mock import patch
from agent.local_supervised_worker_service import run_operator_supervised_worker


class OperatorServiceBoundaryTests(unittest.TestCase):
    @patch("agent.persistent_stop_guard.PersistentStopGuard.require_running")
    @patch("agent.persistent_stop_guard.PersistentStopGuard.__init__", return_value=None)
    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_injected_executor_refused_before_validation(self, validate, init, stop):
        with self.assertRaises(PermissionError):
            run_operator_supervised_worker(
                job_id="job1", journal_path="/private/journal.db",
                server_control_db="/private/stop.db", executor=lambda *a: None)
        validate.assert_not_called()
        stop.assert_not_called()

    @patch("agent.persistent_stop_guard.PersistentStopGuard.require_running")
    @patch("agent.persistent_stop_guard.PersistentStopGuard.__init__", return_value=None)
    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_injected_transport_factory_refused(self, validate, init, stop):
        with self.assertRaises(PermissionError):
            run_operator_supervised_worker(
                job_id="job1", journal_path="/private/journal.db",
                server_control_db="/private/stop.db",
                transport_factory=lambda *a: None)
        validate.assert_not_called()

    @patch("agent.persistent_stop_guard.PersistentStopGuard.require_running",
           side_effect=PermissionError("Emergency stop engaged"))
    @patch("agent.persistent_stop_guard.PersistentStopGuard.__init__", return_value=None)
    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_engaged_stop_prevents_validation_and_execution(self, validate, init, stop):
        with self.assertRaises(PermissionError):
            run_operator_supervised_worker(
                job_id="job1", journal_path="/private/journal.db",
                server_control_db="/private/stop.db")
        validate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
