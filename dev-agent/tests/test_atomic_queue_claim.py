import sqlite3
import tempfile
import unittest
from pathlib import Path
from agent.atomic_queue_claim import claim_admitted_task

class AtomicQueueClaimTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.queue = str(root / "queue.db")
        self.jobs = str(root / "jobs.db")
        self.stop = str(root / "stop.db")
        with sqlite3.connect(self.queue) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT PRIMARY KEY, day_utc TEXT, task TEXT, state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES('job1','2026-11-04','Review tests','queued')")
        with sqlite3.connect(self.jobs) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT PRIMARY KEY, day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES('job1','2026-11-04')")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")

    def claim(self, job_id="job1"):
        return claim_admitted_task(queue_db=self.queue, job_db=self.jobs,
                                   control_db=self.stop, job_id=job_id)

    def state(self):
        with sqlite3.connect(self.queue) as db:
            return db.execute("SELECT state FROM development_tasks WHERE job_id='job1'").fetchone()[0]

    def test_claim_once(self):
        self.assertTrue(self.claim())
        self.assertEqual(self.state(), "claimed")
        self.assertFalse(self.claim())

    def test_stop_preserves_queued(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=1")
        with self.assertRaises(PermissionError):
            self.claim()
        self.assertEqual(self.state(), "queued")

    def test_missing_admission_rolls_back(self):
        with sqlite3.connect(self.jobs) as db:
            db.execute("DELETE FROM admitted_jobs")
        with self.assertRaises(PermissionError):
            self.claim()
        self.assertEqual(self.state(), "queued")

    def test_invalid_job_id_rejected(self):
        with self.assertRaises(ValueError):
            self.claim("../escape")
        self.assertEqual(self.state(), "queued")

    def test_missing_queue_rejected(self):
        Path(self.queue).unlink()
        with self.assertRaises(PermissionError):
            self.claim()
