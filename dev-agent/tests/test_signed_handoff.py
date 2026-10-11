import unittest
from agent.test_jobs import TestJob
from agent.signed_handoff import sign_manifest_job,verify_manifest_job

KEY=b"k"*32
JOB=TestJob("job-1","kyzaswayz12-droid/swayz-ai-bridge","a"*40,"python-unittest")
MANIFEST="b"*64

class SignedHandoffTests(unittest.TestCase):
    def test_roundtrip(self):
        raw,sig=sign_manifest_job(JOB,MANIFEST,KEY)
        self.assertEqual(verify_manifest_job(raw,sig,KEY,MANIFEST),JOB)
    def test_manifest_change_rejected(self):
        raw,sig=sign_manifest_job(JOB,MANIFEST,KEY)
        with self.assertRaises(ValueError):
            verify_manifest_job(raw,sig,KEY,"c"*64)
    def test_bad_signature_rejected(self):
        raw,sig=sign_manifest_job(JOB,MANIFEST,KEY)
        with self.assertRaises(ValueError):
            verify_manifest_job(raw,"0"*64,KEY,MANIFEST)
    def test_tampering_rejected(self):
        raw,sig=sign_manifest_job(JOB,MANIFEST,KEY)
        with self.assertRaises(ValueError):
            verify_manifest_job(raw.replace(b"job-1",b"job-2"),sig,KEY,MANIFEST)
