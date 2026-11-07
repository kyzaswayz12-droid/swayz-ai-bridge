import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from agent.development_task_intake import DevelopmentTaskQueue, provision_task_queue
from agent.held_task_staging import provision_held_tasks, stage_held_task


class HeldTaskStagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.held = str(root / "held.db")
        self.queue = str(root / "executable.db")
        provision_held_tasks(self.held)
        provision_task_queue(self.queue)
        self.args = dict(held_db=self.held, executable_db=self.queue,
                         job_id="slack-123", task="Offline smoke test",
                         now=datetime(2026, 11, 7, tzinfo=timezone.utc))

    def test_staging_does_not_enter_executable_queue(self):
        self.assertEqual(stage_held_task(**self.args)["state"], "held")
        self.assertIsNone(DevelopmentTaskQueue(self.queue).get("slack-123"))
        self.assertFalse(DevelopmentTaskQueue(self.queue).claim("slack-123"))
        with sqlite3.connect(self.held) as db:
            self.assertEqual(db.execute("SELECT state FROM held_tasks").fetchone(), ("held",))

    def test_duplicate_refused(self):
        stage_held_task(**self.args)
        with self.assertRaises(sqlite3.IntegrityError):
            stage_held_task(**self.args)

    def test_existing_executable_job_refused(self):
        with sqlite3.connect(self.queue) as db:
            db.execute("INSERT INTO development_tasks VALUES(?,?,?,?)",
                       ("slack-123", "2026-11-07", "original", "queued"))
        with self.assertRaises(PermissionError):
            stage_held_task(**self.args)

    def test_same_database_refused(self):
        with self.assertRaises(PermissionError):
            stage_held_task(**dict(self.args, held_db=self.queue))

    def test_missing_database_refused(self):
        with self.assertRaises(PermissionError):
            stage_held_task(**dict(self.args, held_db=self.held + ".missing"))

    def test_invalid_task_refused(self):
        with self.assertRaises(ValueError):
            stage_held_task(**dict(self.args, task=" "))
