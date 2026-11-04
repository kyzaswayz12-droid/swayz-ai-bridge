import sqlite3
import tempfile
import unittest
from pathlib import Path
from agent.executor_ledger_compatibility import verify_executor_ledger


class LedgerCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "state.db")

    def create(self, sql):
        with sqlite3.connect(self.path) as db:
            db.execute(sql)

    def test_legacy_tasks_rejected(self):
        self.create("CREATE TABLE tasks(id TEXT)")
        with self.assertRaisesRegex(PermissionError, "Incompatible job"):
            verify_executor_ledger(self.path, "job")

    def test_legacy_usd_budget_rejected(self):
        self.create("CREATE TABLE reservations(request_id TEXT, reserved_usd TEXT)")
        with self.assertRaisesRegex(PermissionError, "Incompatible budget"):
            verify_executor_ledger(self.path, "budget")

    def test_canonical_job_accepted(self):
        self.create("CREATE TABLE admitted_jobs(job_id TEXT, day_utc TEXT)")
        verify_executor_ledger(self.path, "job")

    def test_canonical_budget_accepted(self):
        self.create("CREATE TABLE gbp_reservations(request_id TEXT, provider TEXT, day_utc TEXT, reserved_gbp TEXT, status TEXT, actual_gbp TEXT)")
        verify_executor_ledger(self.path, "budget")

    def test_missing_db_not_created(self):
        with self.assertRaises(PermissionError):
            verify_executor_ledger(self.path, "budget")
        self.assertFalse(Path(self.path).exists())

    def test_partial_schema_rejected(self):
        self.create("CREATE TABLE admitted_jobs(job_id TEXT)")
        with self.assertRaises(PermissionError):
            verify_executor_ledger(self.path, "job")
