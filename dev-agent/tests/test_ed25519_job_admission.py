import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent.ed25519_handoff import sign_job_ed25519
from agent.ed25519_job_admission import accept_ed25519_job
from agent.job_inbox import JobInbox

PAYLOAD = {"job_id": "job1", "repository": "kyzaswayz12-droid/swayz-ai-bridge",
           "commit_sha": "a" * 40, "suite": "python-unittest",
           "manifest_sha256": "b" * 64}


class Ed25519AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.raw, self.sig = sign_job_ed25519(PAYLOAD, self.key)
        self.inbox = JobInbox()

    def tearDown(self):
        self.inbox.close()

    def admit(self, **kwargs):
        args = dict(expected_repository=PAYLOAD["repository"],
                    expected_manifest=PAYLOAD["manifest_sha256"])
        args.update(kwargs)
        return accept_ed25519_job(self.inbox, self.raw, self.sig,
                                  self.key.public_key(), **args)

    def test_valid_job_accepted(self):
        self.assertTrue(self.admit())
        self.assertEqual(self.inbox.status("job1"), "accepted")

    def test_duplicate_job_rejected(self):
        self.assertTrue(self.admit())
        self.assertFalse(self.admit())

    def test_wrong_repository_rejected(self):
        with self.assertRaises(PermissionError):
            self.admit(expected_repository="other/repository")
        self.assertIsNone(self.inbox.status("job1"))

    def test_wrong_manifest_rejected(self):
        with self.assertRaises(PermissionError):
            self.admit(expected_manifest="c" * 64)
        self.assertIsNone(self.inbox.status("job1"))

    def test_invalid_signature_rejected(self):
        with self.assertRaises(ValueError):
            accept_ed25519_job(self.inbox, self.raw, bytes(64),
                               self.key.public_key(),
                               expected_repository=PAYLOAD["repository"],
                               expected_manifest=PAYLOAD["manifest_sha256"])
        self.assertIsNone(self.inbox.status("job1"))
