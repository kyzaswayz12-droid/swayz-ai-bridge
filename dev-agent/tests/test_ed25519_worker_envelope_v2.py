import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent.ed25519_worker_envelope_v2 import sign_worker_envelope_v2, verify_worker_envelope_v2

IMAGE = "sha256:" + "a" * 64
PAYLOAD = {"version": "2", "job_id": "job1",
           "repository": "kyzaswayz12-droid/swayz-ai-bridge",
           "commit_sha": "b" * 40, "suite": "python-unittest",
           "manifest_sha256": "c" * 64, "image_digest": IMAGE}


class Ed25519WorkerEnvelopeV2Tests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.raw, self.sig = sign_worker_envelope_v2(PAYLOAD, self.key)

    def verify(self, **kwargs):
        return verify_worker_envelope_v2(
            self.raw, self.sig, self.key.public_key(),
            expected_image_digest=kwargs.get("image", IMAGE))

    def test_signed_image_matches(self):
        self.assertEqual(self.verify()["image_digest"], IMAGE)

    def test_different_approved_image_rejected(self):
        with self.assertRaises(PermissionError):
            self.verify(image="sha256:" + "d" * 64)

    def test_modified_image_bytes_rejected(self):
        with self.assertRaises(ValueError):
            verify_worker_envelope_v2(
                self.raw.replace(IMAGE.encode(), ("sha256:" + "d" * 64).encode()),
                self.sig, self.key.public_key(), expected_image_digest=IMAGE)

    def test_legacy_envelope_rejected(self):
        with self.assertRaises(ValueError):
            sign_worker_envelope_v2({k:v for k,v in PAYLOAD.items() if k != "image_digest"}, self.key)

    def test_invalid_version_rejected(self):
        with self.assertRaises(ValueError):
            sign_worker_envelope_v2({**PAYLOAD, "version": "1"}, self.key)
