import sqlite3
import tempfile
import unittest
from pathlib import Path
from agent.queue_handoff_readiness import inspect_handoff_readiness

class HandoffReadinessTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.queue = str(root / "queue.db")
        self.jobs = str(root / "jobs.db")
        self.stop = str(root / "stop.db")
        with sqlite3.connect(self.queue) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT,day_utc TEXT,state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES('j1','2026-11-04','claimed')")
        with sqlite3.connect(self.jobs) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT,day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES('j1','2026-11-04')")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")

    def check(self, job_id="j1"):
        return inspect_handoff_readiness(job_id=job_id, queue_db=self.queue,
                                         job_db=self.jobs, control_db=self.stop)

    def test_claimed_admitted_job_requires_operator(self):
        self.assertEqual(self.check()["state"], "requires_operator_signed_handoff")

    def test_queued_job_rejected(self):
        with sqlite3.connect(self.queue) as db:
            db.execute("UPDATE development_tasks SET state='queued'")
        with self.assertRaises(PermissionError):
            self.check()

    def test_unadmitted_job_rejected(self):
        with sqlite3.connect(self.jobs) as db:
            db.execute("DELETE FROM admitted_jobs")
        with self.assertRaises(PermissionError):
            self.check()

    def test_stop_rejected(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=1")
        with self.assertRaises(PermissionError):
            self.check()

    def test_invalid_id_rejected(self):
        with self.assertRaises(ValueError):
            self.check("../j1")
