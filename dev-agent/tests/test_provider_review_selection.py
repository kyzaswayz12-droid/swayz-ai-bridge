import sqlite3
import tempfile
import unittest
from pathlib import Path
from agent.offline_queue_coordinator import select_for_provider_review
from agent.development_task_intake import DevelopmentTaskQueue

class ProviderReviewSelectionTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.queue,self.jobs,self.stop=[str(root / n) for n in ("queue.db","jobs.db","stop.db")]
        with sqlite3.connect(self.queue) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT PRIMARY KEY,day_utc TEXT,task TEXT,state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES('j1','2026-11-04','Fix test','queued')")
        with sqlite3.connect(self.jobs) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT PRIMARY KEY,day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES('j1','2026-11-04')")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")

    def select(self):
        return select_for_provider_review(queue_db=self.queue,job_db=self.jobs,control_db=self.stop)

    def test_provider_selection_preserves_queued_state(self):
        self.assertEqual(self.select()["state"], "queued_for_review")
        self.assertEqual(DevelopmentTaskQueue(self.queue).get("j1")["state"], "queued")

    def test_existing_cycle_can_claim_after_review(self):
        self.select()
        q = DevelopmentTaskQueue(self.queue)
        self.assertTrue(q.claim("j1"))
        self.assertFalse(q.claim("j1"))

    def test_missing_admission_rejected(self):
        with sqlite3.connect(self.jobs) as db:
            db.execute("DELETE FROM admitted_jobs")
        with self.assertRaises(PermissionError):
            self.select()

    def test_stop_blocks_review_selection(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=1")
        with self.assertRaises(PermissionError):
            self.select()

    def test_no_queued_task(self):
        with sqlite3.connect(self.queue) as db:
            db.execute("UPDATE development_tasks SET state='claimed'")
        self.assertEqual(self.select(), {"state": "empty"})
