import sqlite3
import tempfile
import unittest
from pathlib import Path
from agent.queue_selection import next_queued_job

class QueueSelectionHardeningTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.queue, self.jobs, self.stop = (str(root / x) for x in ("q.db","j.db","s.db"))
        with sqlite3.connect(self.queue) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT,day_utc TEXT,task TEXT,state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES('j1','2026-11-04','Review','queued')")
        with sqlite3.connect(self.jobs) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT,day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES('j1','2026-11-04')")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")

    def select(self):
        return next_queued_job(queue_db=self.queue,job_db=self.jobs,control_db=self.stop)

    def test_valid_selection(self):
        self.assertEqual(self.select(), {"job_id":"j1","task":"Review"})

    def test_invalid_task_rejected(self):
        with sqlite3.connect(self.queue) as db:
            db.execute("UPDATE development_tasks SET task=' '")
        with self.assertRaises(PermissionError):
            self.select()

    def test_invalid_id_rejected(self):
        with sqlite3.connect(self.queue) as db:
            db.execute("UPDATE development_tasks SET job_id='../bad'")
        with self.assertRaises(PermissionError):
            self.select()

    def test_incompatible_queue_schema_rejected(self):
        with sqlite3.connect(self.queue) as db:
            db.execute("DROP TABLE development_tasks")
            db.execute("CREATE TABLE development_tasks(job_id TEXT)")
        with self.assertRaises(PermissionError):
            self.select()

    def test_incompatible_admission_schema_rejected(self):
        with sqlite3.connect(self.jobs) as db:
            db.execute("DROP TABLE admitted_jobs")
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT)")
        with self.assertRaises(PermissionError):
            self.select()
