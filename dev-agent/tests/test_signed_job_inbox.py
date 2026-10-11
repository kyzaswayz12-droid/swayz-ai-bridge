import tempfile
import unittest
from pathlib import Path
from agent.test_jobs import TestJob
from agent.signed_handoff import sign_manifest_job
from agent.job_inbox import JobInbox
from agent.signed_job_inbox import admit_signed_handoff

KEY=b"k"*32
JOB=TestJob("job-1","kyzaswayz12-droid/swayz-ai-bridge","a"*40,"python-unittest")
MANIFEST="b"*64

class SignedInboxTests(unittest.TestCase):
    def test_replay_rejected_across_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/"inbox.db")
            raw,sig=sign_manifest_job(JOB,MANIFEST,KEY)
            inbox=JobInbox(path)
            self.assertTrue(admit_signed_handoff(inbox,raw,sig,KEY,MANIFEST))
            self.assertFalse(admit_signed_handoff(inbox,raw,sig,KEY,MANIFEST))
            inbox.close()
            inbox=JobInbox(path)
            self.assertFalse(admit_signed_handoff(inbox,raw,sig,KEY,MANIFEST))
            inbox.close()
    def test_bad_manifest_not_admitted(self):
        inbox=JobInbox()
        raw,sig=sign_manifest_job(JOB,MANIFEST,KEY)
        with self.assertRaises(ValueError):
            admit_signed_handoff(inbox,raw,sig,KEY,"c"*64)
        self.assertIsNone(inbox.status("job-1"))
        inbox.close()
    def test_bad_signature_not_admitted(self):
        inbox=JobInbox()
        raw,sig=sign_manifest_job(JOB,MANIFEST,KEY)
        with self.assertRaises(ValueError):
            admit_signed_handoff(inbox,raw,"0"*64,KEY,MANIFEST)
        self.assertIsNone(inbox.status("job-1"))
        inbox.close()
