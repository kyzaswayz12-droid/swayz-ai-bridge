import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from agent.development_task_intake import provision_task_queue, submit_verified_task


class DevelopmentTaskIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.queue = str(root / "queue.db")
        self.jobs = str(root / "jobs.db")
        self.stop = str(root / "stop.db")
        provision_task_queue(self.queue)
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY, stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")
        self.now = datetime(2026, 11, 4, 20, tzinfo=timezone.utc)

    def submit(self, **kw):
        args = dict(db_path=self.queue, job_db=self.jobs,
                    control_db=self.stop, job_id="task1",
                    task="Fix the test suite", now=self.now)
        args.update(kw)
        return submit_verified_task(**args)

    def test_queued_and_admitted(self):
        self.assertEqual(self.submit(), "task1")
        with sqlite3.connect(self.queue) as db:
            self.assertEqual(db.execute(
                "SELECT state FROM development_tasks WHERE job_id='task1'"
            ).fetchone(), ("queued",))
        with sqlite3.connect(self.jobs) as db:
            self.assertEqual(db.execute(
                "SELECT day_utc FROM admitted_jobs WHERE job_id='task1'"
            ).fetchone(), ("2026-11-04",))

    def test_stop_rejects_before_admission(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=1")
        with self.assertRaises(PermissionError):
            self.submit()
        self.assertFalse(Path(self.jobs).exists())

    def test_duplicate_refused(self):
        self.submit()
        with self.assertRaises(PermissionError):
            self.submit()

    def test_invalid_task_rejected(self):
        with self.assertRaises(ValueError):
            self.submit(task=" ")

    def test_missing_queue_refused(self):
        Path(self.queue).unlink()
        with self.assertRaises(PermissionError):
            self.submit()
        self.assertFalse(Path(self.jobs).exists())
