import sqlite3
import tempfile
import unittest
from pathlib import Path
from agent.queue_selection import next_queued_job

class QueueSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.queue, self.jobs, self.stop = [str(root / name) for name in ("queue.db", "jobs.db", "stop.db")]
        with sqlite3.connect(self.queue) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT,day_utc TEXT,task TEXT,state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES('j1','2026-11-04','Test change','queued')")
        with sqlite3.connect(self.jobs) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT,day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES('j1','2026-11-04')")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")

    def select(self):
        return next_queued_job(queue_db=self.queue,job_db=self.jobs,control_db=self.stop)

    def test_selects_admitted_job_without_mutation(self):
        self.assertEqual(self.select(), {"job_id":"j1","task":"Test change"})
        with sqlite3.connect(self.queue) as db:
            self.assertEqual(db.execute("SELECT state FROM development_tasks").fetchone(), ("queued",))

    def test_stop_blocks_selection(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=1")
        with self.assertRaises(PermissionError):
            self.select()

    def test_orphaned_admission_rejected(self):
        with sqlite3.connect(self.jobs) as db:
            db.execute("DELETE FROM admitted_jobs")
        with self.assertRaises(PermissionError):
            self.select()

    def test_no_queued_job(self):
        with sqlite3.connect(self.queue) as db:
            db.execute("UPDATE development_tasks SET state='done'")
        self.assertIsNone(self.select())

    def test_missing_database_rejected(self):
        Path(self.jobs).unlink()
        with self.assertRaises(PermissionError):
            self.select()
