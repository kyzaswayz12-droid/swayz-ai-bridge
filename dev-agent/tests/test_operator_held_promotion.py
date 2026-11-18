import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from agent.development_task_intake import provision_task_queue
from agent.held_task_staging import provision_held_tasks, stage_held_task
from agent.operator_held_promotion import promote_held_task
from agent.emergency_stop import EmergencyStop


class OperatorHeldPromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.held = str(root / "held.db")
        self.task = str(root / "task.db")
        self.jobs = str(root / "jobs.db")
        self.stop = str(root / "stop.db")
        provision_held_tasks(self.held)
        provision_task_queue(self.task)
        with sqlite3.connect(self.jobs) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT PRIMARY KEY, day_utc TEXT NOT NULL)")
        s = EmergencyStop(self.stop)
        s.close()
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        stage_held_task(held_db=self.held, executable_db=self.task,
                        job_id="slack-test", task="Offline acceptance only",
                        now=self.now)

    def tearDown(self):
        self.temp.cleanup()

    def promote(self, **kwargs):
        params = dict(held_db=self.held, executable_db=self.task, job_db=self.jobs,
                      stop_db=self.stop, job_id="slack-test",
                      now=self.now, operator_approved=True)
        params.update(kwargs)
        with patch("agent.operator_held_promotion.os.geteuid", return_value=0):
            return promote_held_task(**params)

    def test_engaged_stop_refuses_promotion(self):
        with self.assertRaises(PermissionError):
            self.promote()
        with sqlite3.connect(self.task) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM development_tasks").fetchone()[0], 0)

    def test_approval_required(self):
        with self.assertRaises(PermissionError):
            self.promote(operator_approved=False)

    def test_promotes_once_without_execution_or_stop_release(self):
        stop = EmergencyStop(self.stop)
        stop.enable(owner_authorised=True)
        stop.close()
        self.assertEqual(self.promote()["state"], "queued")
        with sqlite3.connect(self.task) as db:
            self.assertEqual(db.execute("SELECT state FROM development_tasks WHERE job_id='slack-test'").fetchone()[0], "queued")
        with sqlite3.connect(self.held) as db:
            self.assertEqual(db.execute("SELECT state FROM held_tasks WHERE job_id='slack-test'").fetchone()[0], "held")
        with sqlite3.connect(self.jobs) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM admitted_jobs").fetchone()[0], 1)
        with self.assertRaises(PermissionError):
            self.promote()
        stop = EmergencyStop(self.stop)
        self.assertFalse(stop.is_stopped())
        stop.stop()
        stop.close()

    def test_rejects_same_database(self):
        with self.assertRaises(PermissionError):
            self.promote(job_db=self.held)
