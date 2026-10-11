import tempfile
import unittest
from pathlib import Path
from agent.job_inbox import JobInbox
from agent.test_jobs import TestJob,serialize_job,sign_job

KEY=b"x"*32
JOB=TestJob("job-001","kyzaswayz12-droid/swayz-ai-bridge","a"*40,"python-unittest")

class JobInboxTests(unittest.TestCase):
    def test_durable_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/"jobs.db")
            raw=serialize_job(JOB)
            signature=sign_job(JOB,KEY)
            inbox=JobInbox(path)
            self.assertTrue(inbox.accept(raw,signature,KEY))
            self.assertFalse(inbox.accept(raw,signature,KEY))
            inbox.close()
            inbox=JobInbox(path)
            self.assertEqual(inbox.status("job-001"),"accepted")
            self.assertFalse(inbox.accept(raw,signature,KEY))
            inbox.close()

    def test_bad_signature_not_admitted(self):
        inbox=JobInbox()
        with self.assertRaises(ValueError):
            inbox.accept(serialize_job(JOB),"0"*64,KEY)
        self.assertIsNone(inbox.status("job-001"))
        inbox.close()
