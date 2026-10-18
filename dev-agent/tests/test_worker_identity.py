import unittest
from agent.test_jobs import TestJob
from agent.signed_handoff import sign_manifest_job
from agent.worker_identity import verify_worker_identity

SECRET = b"s" * 32
SHA = "a" * 40
MANIFEST = "b" * 64


class WorkerIdentityTests(unittest.TestCase):
    def setUp(self):
        self.raw, self.signature = sign_manifest_job(
            TestJob("job1", "kyzaswayz12-droid/swayz-ai-bridge",
                    SHA, "python-unittest"), MANIFEST, SECRET)

    def verify(self, **overrides):
        args = dict(raw=self.raw, signature=self.signature, secret=SECRET,
                    manifest_sha256=MANIFEST, expected_job_id="job1",
                    observed_commit_sha=SHA)
        args.update(overrides)
        return verify_worker_identity(**args)

    def test_matching_identity(self):
        self.assertEqual(self.verify().commit_sha, SHA)

    def test_wrong_job_rejected(self):
        with self.assertRaises(PermissionError):
            self.verify(expected_job_id="job2")

    def test_wrong_commit_rejected(self):
        with self.assertRaises(PermissionError):
            self.verify(observed_commit_sha="c" * 40)

    def test_wrong_signature_rejected(self):
        with self.assertRaises(ValueError):
            self.verify(signature="0" * 64)
