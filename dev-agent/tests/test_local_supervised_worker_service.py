"""Supervised service integration tests: no Docker, network or paid APIs."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from agent.worker_journal import WorkerJournal
from agent.local_supervised_worker_service import run_local_supervised_worker


class FakeTransport:
    def daemon_healthy(self):
        return True


class LocalSupervisedWorkerServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal_path = str(Path(self.temp.name) / "journal.db")
        db = WorkerJournal(self.journal_path)
        self.assertTrue(db.record_admission("job1"))
        db.close()
        self.factory_calls = []
        self.runner_calls = []

    def factory(self, plan, *, server_control_db):
        self.factory_calls.append((plan, server_control_db))
        return FakeTransport()

    def runner(self, plan, *, transport, daemon_probe):
        self.runner_calls.append(plan)
        return SimpleNamespace(state="passed", exit_code=0,
                               output="ok", cleanup_verified=True,
                               docker_executed=False)

    def invoke(self, **changes):
        args = dict(job_id="job1", journal_path=self.journal_path,
                    server_control_db="/server/control.db",
                    transport_factory=self.factory, lifecycle_runner=self.runner)
        args.update(changes)
        return run_local_supervised_worker(**args)

    def status(self):
        db = WorkerJournal(self.journal_path)
        try:
            return db.status("job1")[0]
        finally:
            db.close()

    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_success_records_passed(self, gate):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(
            executes=False, name="swayz-test-job1"))
        result = self.invoke()
        self.assertEqual(result.state, "passed")
        self.assertEqual(self.status(), "passed")
        self.assertEqual(len(self.runner_calls), 1)

    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_failed_gate_never_claims_job(self, gate):
        gate.side_effect = PermissionError("stop engaged")
        with self.assertRaises(PermissionError):
            self.invoke()
        self.assertEqual(self.status(), "admitted")
        self.assertEqual(self.factory_calls, [])

    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_cleanup_unverified_blocks_job(self, gate):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(
            executes=False, name="swayz-test-job1"))
        def bad_cleanup(plan, **kwargs):
            return SimpleNamespace(state="passed", exit_code=0,
                output="ok", cleanup_verified=False, docker_executed=True)
        result = self.invoke(lifecycle_runner=bad_cleanup)
        self.assertEqual(result.state, "blocked")
        self.assertEqual(self.status(), "blocked")

    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_executor_exception_blocks_job(self, gate):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(
            executes=False, name="swayz-test-job1"))
        def fail(plan, **kwargs):
            raise RuntimeError("transport failed")
        with self.assertRaises(RuntimeError):
            self.invoke(lifecycle_runner=fail)
        self.assertEqual(self.status(), "blocked")

    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_duplicate_job_not_reexecuted(self, gate):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(
            executes=False, name="swayz-test-job1"))
        self.invoke()
        with self.assertRaises(PermissionError):
            self.invoke()
        self.assertEqual(len(self.runner_calls), 1)

    @patch("agent.local_supervised_worker_service.validate_reserved_signed_worker_plan")
    def test_control_path_cannot_be_overridden(self, gate):
        with self.assertRaises(PermissionError):
            self.invoke(control_db="/attacker/control.db")
        gate.assert_not_called()
