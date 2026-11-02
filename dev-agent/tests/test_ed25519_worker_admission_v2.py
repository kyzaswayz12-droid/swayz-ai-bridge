import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent.ed25519_worker_envelope_v2 import sign_worker_envelope_v2
from agent.ed25519_worker_admission_v2 import admit_worker_envelope_v2
from agent.job_inbox import JobInbox

IMAGE = "sha256:" + "a" * 64
SHA = "b" * 40
MANIFEST = "c" * 64
PAYLOAD = {"version": "2", "job_id": "job1",
           "repository": "kyzaswayz12-droid/swayz-ai-bridge",
           "commit_sha": SHA, "suite": "python-unittest",
           "manifest_sha256": MANIFEST, "image_digest": IMAGE}


class WorkerAdmissionV2Tests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.raw, self.sig = sign_worker_envelope_v2(PAYLOAD, self.key)
        self.inbox = JobInbox()

    def tearDown(self):
        self.inbox.close()

    def admit(self, **changes):
        params = dict(expected_manifest=MANIFEST, expected_commit=SHA,
                      expected_image_digest=IMAGE,
                      approved_image_digests=frozenset({IMAGE}))
        params.update(changes)
        return admit_worker_envelope_v2(
            self.inbox, self.raw, self.sig, self.key.public_key(), **params)

    def test_valid_admission(self):
        self.assertTrue(self.admit())

    def test_replay_rejected(self):
        self.assertTrue(self.admit())
        self.assertFalse(self.admit())

    def test_image_not_allowlisted(self):
        with self.assertRaises(PermissionError):
            self.admit(approved_image_digests=frozenset())

    def test_wrong_commit(self):
        with self.assertRaises(PermissionError):
            self.admit(expected_commit="d" * 40)

    def test_wrong_manifest(self):
        with self.assertRaises(PermissionError):
            self.admit(expected_manifest="e" * 64)

    def test_wrong_image(self):
        with self.assertRaises(PermissionError):
            self.admit(expected_image_digest="sha256:" + "f" * 64)
