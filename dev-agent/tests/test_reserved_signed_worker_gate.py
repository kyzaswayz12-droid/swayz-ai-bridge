"""Offline quota and GBP budget gate tests; no Docker or provider calls."""
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from agent.trusted_docker_executor import validate_reserved_signed_worker_plan


class ReservedSignedWorkerGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.jobs = Path(self.tmp.name) / "jobs.db"
        self.budget = Path(self.tmp.name) / "budget.db"
        self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
        with sqlite3.connect(self.jobs) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT PRIMARY KEY, day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES('job1','2026-11-03')")
        with sqlite3.connect(self.budget) as db:
            db.execute("CREATE TABLE gbp_reservations(request_id TEXT PRIMARY KEY, provider TEXT, day_utc TEXT, reserved_gbp TEXT, status TEXT, actual_gbp TEXT)")
            db.execute("INSERT INTO gbp_reservations VALUES('request1','openai','2026-11-03','0.25','reserved',NULL)")

    def validate(self, **changes):
        args = dict(job_db=str(self.jobs), budget_db=str(self.budget),
                    request_id="request1", provider="openai", now=self.now,
                    job_id="job1")
        args.update(changes)
        return validate_reserved_signed_worker_plan(**args)

    @patch("agent.trusted_docker_executor.validate_signed_admitted_worker_plan")
    def test_valid_reservation_reaches_signed_gate(self, gate):
        self.validate()
        gate.assert_called_once_with(job_id="job1")

    @patch("agent.trusted_docker_executor.validate_signed_admitted_worker_plan")
    def test_missing_job_admission_rejected(self, gate):
        with self.assertRaises(PermissionError):
            self.validate(job_id="unknown")
        gate.assert_not_called()

    @patch("agent.trusted_docker_executor.validate_signed_admitted_worker_plan")
    def test_wrong_provider_rejected(self, gate):
        with self.assertRaises(PermissionError):
            self.validate(provider="anthropic")
        gate.assert_not_called()

    @patch("agent.trusted_docker_executor.validate_signed_admitted_worker_plan")
    def test_over_budget_rejected(self, gate):
        with sqlite3.connect(self.budget) as db:
            db.execute("UPDATE gbp_reservations SET reserved_gbp='5.01'")
        with self.assertRaises(PermissionError):
            self.validate()
        gate.assert_not_called()

    @patch("agent.trusted_docker_executor.validate_signed_admitted_worker_plan")
    def test_job_quota_exceeded_rejected(self, gate):
        with sqlite3.connect(self.jobs) as db:
            db.executemany("INSERT INTO admitted_jobs VALUES (?, '2026-11-03')",
                           [(f"job{i}",) for i in range(2, 22)])
        with self.assertRaises(PermissionError):
            self.validate()
        gate.assert_not_called()

    @patch("agent.trusted_docker_executor.validate_signed_admitted_worker_plan")
    def test_settled_reservation_rejected(self, gate):
        with sqlite3.connect(self.budget) as db:
            db.execute("UPDATE gbp_reservations SET status='settled',actual_gbp='0.20'")
        with self.assertRaises(PermissionError):
            self.validate()
        gate.assert_not_called()

    @patch("agent.trusted_docker_executor.validate_signed_admitted_worker_plan")
    def test_missing_ledger_rejected_without_creation(self, gate):
        missing = Path(self.tmp.name) / "missing.db"
        with self.assertRaises(PermissionError):
            self.validate(budget_db=str(missing))
        self.assertFalse(missing.exists())
        gate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
