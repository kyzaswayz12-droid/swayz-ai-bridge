import unittest
from agent.test_jobs import TestJob,serialize_job,sign_job,verify_job

KEY=b"x"*32
JOB=TestJob("test-001","kyzaswayz12-droid/swayz-ai-bridge","a"*40,"python-unittest")

class TestJobsTests(unittest.TestCase):
    def test_signed_roundtrip(self):
        raw=serialize_job(JOB)
        self.assertEqual(verify_job(raw,sign_job(JOB,KEY),KEY),JOB)

    def test_tampering_rejected(self):
        raw=serialize_job(JOB)
        signature=sign_job(JOB,KEY)
        with self.assertRaises(ValueError):
            verify_job(raw.replace(b"test-001",b"test-002"),signature,KEY)

    def test_wrong_secret_rejected(self):
        raw=serialize_job(JOB)
        with self.assertRaises(ValueError):
            verify_job(raw,sign_job(JOB,KEY),b"y"*32)

    def test_invalid_repository_and_suite_rejected(self):
        for job in (TestJob("job","other/repo","a"*40,"python-unittest"),
                    TestJob("job",JOB.repository,"a"*40,"shell")):
            with self.assertRaises(ValueError):
                serialize_job(job)

    def test_short_secret_rejected(self):
        with self.assertRaises(ValueError):
            sign_job(JOB,b"short")
