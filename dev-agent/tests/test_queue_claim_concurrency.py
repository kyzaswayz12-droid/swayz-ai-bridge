import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from agent.atomic_queue_claim import claim_admitted_task

class QueueClaimConcurrencyTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.queue, self.jobs, self.stop = [str(root / x) for x in ("queue.db","jobs.db","stop.db")]
        with sqlite3.connect(self.queue) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT PRIMARY KEY,day_utc TEXT,task TEXT,state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES('job1','2026-11-04','Repair tests','queued')")
        with sqlite3.connect(self.jobs) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT PRIMARY KEY,day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES('job1','2026-11-04')")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")

    def claim(self):
        return claim_admitted_task(queue_db=self.queue,job_db=self.jobs,control_db=self.stop,job_id="job1")

    def test_competing_claimants_only_one_wins(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: self.claim(), range(6)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 5)

    def test_malformed_task_does_not_claim(self):
        with sqlite3.connect(self.queue) as db:
            db.execute("UPDATE development_tasks SET task=' '")
        with self.assertRaises(PermissionError):
            self.claim()
        with sqlite3.connect(self.queue) as db:
            self.assertEqual(db.execute("SELECT state FROM development_tasks").fetchone(), ("queued",))

    def test_corrupt_admission_schema_fails_closed(self):
        with sqlite3.connect(self.jobs) as db:
            db.execute("DROP TABLE admitted_jobs")
        with self.assertRaises(PermissionError):
            self.claim()
