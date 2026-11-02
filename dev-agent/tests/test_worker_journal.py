import tempfile
import unittest
from pathlib import Path
from agent.worker_journal import WorkerJournal


class WorkerJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "worker.sqlite")

    def tearDown(self):
        self.temp.cleanup()

    def test_durable_success(self):
        journal = WorkerJournal(self.path)
        self.assertTrue(journal.record_admission("job1"))
        journal.transition("job1", "admitted", "running")
        journal.close()
        reopened = WorkerJournal(self.path)
        reopened.transition("job1", "running", "passed", exit_code=0, excerpt="OK")
        self.assertEqual(reopened.status("job1"), ("passed", 0, "OK"))
        reopened.close()

    def test_duplicate_job_rejected(self):
        journal = WorkerJournal(self.path)
        self.assertTrue(journal.record_admission("job1"))
        self.assertFalse(journal.record_admission("job1"))
        journal.close()

    def test_invalid_transition_rejected(self):
        journal = WorkerJournal(self.path)
        journal.record_admission("job1")
        with self.assertRaises(ValueError):
            journal.transition("job1", "admitted", "passed")
        journal.close()

    def test_restart_blocks_incomplete_jobs(self):
        journal = WorkerJournal(self.path)
        journal.record_admission("job1")
        journal.record_admission("job2")
        journal.transition("job2", "admitted", "running")
        journal.close()
        reopened = WorkerJournal(self.path)
        self.assertEqual(reopened.recover_incomplete(), 2)
        self.assertEqual(reopened.status("job1")[0], "blocked")
        self.assertEqual(reopened.status("job2")[0], "blocked")
        reopened.close()

    def test_terminal_result_cannot_be_overwritten(self):
        journal = WorkerJournal(self.path)
        journal.record_admission("job1")
        journal.transition("job1", "admitted", "running")
        journal.transition("job1", "running", "failed", exit_code=1)
        with self.assertRaises(PermissionError):
            journal.transition("job1", "running", "passed", exit_code=0)
        journal.close()
