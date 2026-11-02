import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent.ed25519_handoff import sign_job_ed25519, verify_job_ed25519

PAYLOAD = {"job_id": "job1", "repository": "kyzaswayz12-droid/swayz-ai-bridge",
           "commit_sha": "a" * 40, "suite": "python-unittest",
           "manifest_sha256": "b" * 64}


class Ed25519HandoffTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key()
        self.raw, self.signature = sign_job_ed25519(PAYLOAD, self.private)

    def test_valid_signature(self):
        self.assertEqual(verify_job_ed25519(self.raw, self.signature, self.public), PAYLOAD)

    def test_tampered_payload_rejected(self):
        with self.assertRaises(ValueError):
            verify_job_ed25519(self.raw.replace(b"job1", b"job2"), self.signature, self.public)

    def test_wrong_public_key_rejected(self):
        with self.assertRaises(ValueError):
            verify_job_ed25519(self.raw, self.signature, Ed25519PrivateKey.generate().public_key())

    def test_modified_signature_rejected(self):
        with self.assertRaises(ValueError):
            verify_job_ed25519(self.raw, bytes(64), self.public)

    def test_extra_field_rejected(self):
        with self.assertRaises(ValueError):
            sign_job_ed25519({**PAYLOAD, "command": "docker run --privileged"}, self.private)
