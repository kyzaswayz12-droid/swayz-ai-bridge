"""Operator execution service tests; no real Docker commands."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from agent.worker_journal import WorkerJournal
from agent.local_supervised_worker_service import run_operator_supervised_worker


class OperatorServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.journal_path = str(Path(self.tmp.name) / "journal.db")
        self.control_path = str(Path(self.tmp.name) / "stop.db")
        with sqlite3.connect(self.control_path) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY, stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES (1,0)")
        journal = WorkerJournal(self.journal_path)
        journal.record_admission("job1")
        journal.close()

    def status(self):
        journal = WorkerJournal(self.journal_path)
        try:
            return journal.status("job1")[0]
        finally:
            journal.close()

    def invoke(self, **extra):
        return run_operator_supervised_worker(
            job_id="job1", journal_path=self.journal_path,
            server_control_db=self.control_path, **extra)

    @patch("agent.local_supervised_worker_service.run_supervised_lifecycle")
    @patch("agent.local_supervised_worker_service.FixedDockerTransport")
    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_validated_job_executes_once(self, gate, transport, runner):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(
            name="swayz-test-job1", executes=False))
        transport.return_value.daemon_healthy.return_value = True
        runner.return_value = SimpleNamespace(
            state="passed", cleanup_verified=True, exit_code=0, output="ok")
        outcome = self.invoke()
        self.assertEqual(outcome.state, "passed")
        self.assertEqual(self.status(), "passed")
        runner.assert_called_once()
        with self.assertRaises(PermissionError):
            self.invoke()
        self.assertEqual(runner.call_count, 1)

    @patch("agent.local_supervised_worker_service.run_supervised_lifecycle")
    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_engaged_stop_rejects_before_validation(self, gate, runner):
        with sqlite3.connect(self.control_path) as db:
            db.execute("UPDATE agent_control SET stopped=1 WHERE id=1")
        with self.assertRaises(PermissionError):
            self.invoke()
        gate.assert_not_called()
        runner.assert_not_called()

    @patch("agent.local_supervised_worker_service.run_supervised_lifecycle")
    @patch("agent.local_supervised_worker_service.FixedDockerTransport")
    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_cleanup_failure_blocks_job(self, gate, transport, runner):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(
            name="swayz-test-job1", executes=False))
        runner.return_value = SimpleNamespace(
            state="cleanup_unverified", cleanup_verified=False,
            exit_code=None, output="")
        self.assertEqual(self.invoke().state, "blocked")
        self.assertEqual(self.status(), "blocked")

    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_cannot_override_server_owned_state(self, gate):
        with self.assertRaises(PermissionError):
            self.invoke(control_db="/tmp/fake")
        gate.assert_not_called()
