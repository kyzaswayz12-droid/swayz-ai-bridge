import sqlite3
import tempfile
import unittest
from pathlib import Path
from agent.queue_recovery_review import inspect_claimed_tasks

class QueueRecoveryReviewTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.queue = str(root / "queue.db")
        self.journal = str(root / "journal.db")
        self.stop = str(root / "stop.db")
        with sqlite3.connect(self.queue) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT,state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES('j1','claimed')")
        with sqlite3.connect(self.journal) as db:
            db.execute("CREATE TABLE worker_jobs(job_id TEXT PRIMARY KEY,state TEXT)")
            db.execute("INSERT INTO worker_jobs VALUES('j1','running')")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")

    def review(self):
        return inspect_claimed_tasks(queue_db=self.queue,journal_db=self.journal,control_db=self.stop)

    def test_claimed_job_requires_manual_reconciliation(self):
        self.assertEqual(self.review(), [{"job_id":"j1","journal_state":"running",
                                          "action":"manual_reconciliation_required"}])
        with sqlite3.connect(self.queue) as db:
            self.assertEqual(db.execute("SELECT state FROM development_tasks").fetchone(), ("claimed",))

    def test_missing_journal_entry_is_not_requeued(self):
        with sqlite3.connect(self.journal) as db:
            db.execute("DELETE FROM worker_jobs")
        self.assertEqual(self.review()[0]["journal_state"], "missing")

    def test_stop_blocks_recovery_inspection(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=1")
        with self.assertRaises(PermissionError):
            self.review()

    def test_missing_journal_file_fails_closed(self):
        Path(self.journal).unlink()
        with self.assertRaises(PermissionError):
            self.review()

    def test_no_claimed_tasks(self):
        with sqlite3.connect(self.queue) as db:
            db.execute("UPDATE development_tasks SET state='done'")
        self.assertEqual(self.review(), [])
