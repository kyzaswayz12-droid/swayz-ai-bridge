import sqlite3
import tempfile
import unittest
from pathlib import Path
from agent.offline_queue_coordinator import prepare_next_handoff

class OfflineQueueCoordinatorTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.queue = str(root / "queue.db")
        self.jobs = str(root / "jobs.db")
        self.stop = str(root / "stop.db")
        with sqlite3.connect(self.queue) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT PRIMARY KEY,day_utc TEXT,task TEXT,state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES('j1','2026-11-04','Fix unit tests','queued')")
        with sqlite3.connect(self.jobs) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT PRIMARY KEY,day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES('j1','2026-11-04')")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")

    def prepare(self):
        return prepare_next_handoff(queue_db=self.queue,job_db=self.jobs,control_db=self.stop)

    def test_offline_handoff_requires_operator(self):
        result = self.prepare()
        self.assertEqual(result["state"], "requires_operator_signed_handoff")
        self.assertEqual(result["job_id"], "j1")
        with sqlite3.connect(self.queue) as db:
            self.assertEqual(db.execute("SELECT state FROM development_tasks").fetchone(), ("claimed",))

    def test_second_pass_never_replays_claim(self):
        self.prepare()
        self.assertEqual(self.prepare(), {"state": "empty"})

    def test_stop_blocks_before_claim(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=1")
        with self.assertRaises(PermissionError):
            self.prepare()
        with sqlite3.connect(self.queue) as db:
            self.assertEqual(db.execute("SELECT state FROM development_tasks").fetchone(), ("queued",))

    def test_missing_admission_does_not_claim(self):
        with sqlite3.connect(self.jobs) as db:
            db.execute("DELETE FROM admitted_jobs")
        with self.assertRaises(PermissionError):
            self.prepare()
        with sqlite3.connect(self.queue) as db:
            self.assertEqual(db.execute("SELECT state FROM development_tasks").fetchone(), ("queued",))

    def test_empty_queue(self):
        with sqlite3.connect(self.queue) as db:
            db.execute("UPDATE development_tasks SET state='done'")
        self.assertEqual(self.prepare(), {"state": "empty"})
