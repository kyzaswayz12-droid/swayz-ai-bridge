"""Signed identity checks before offline worker validation; never runs Docker."""
import hashlib
import hmac
import json
import unittest
from unittest.mock import patch

from agent.test_jobs import TestJob
from agent.signed_handoff import sign_manifest_job
from agent.trusted_docker_executor import validate_signed_admitted_worker_plan

SECRET = b"s" * 32
MANIFEST = "a" * 64
COMMIT = "b" * 40
REPO = "kyzaswayz12-droid/swayz-ai-bridge"


class SignedWorkerGateTests(unittest.TestCase):
    def setUp(self):
        self.raw, self.signature = sign_manifest_job(
            TestJob("job1", REPO, COMMIT, "python-unittest"), MANIFEST, SECRET)

    def validate(self, **overrides):
        args = dict(raw=self.raw, signature=self.signature, secret=SECRET,
                    expected_manifest=MANIFEST, expected_repository=REPO,
                    expected_commit_sha=COMMIT, job_id="job1",
                    control_db="/not-used", journal_db="/not-used")
        args.update(overrides)
        return validate_signed_admitted_worker_plan(**args)

    @patch("agent.trusted_docker_executor.validate_admitted_worker_plan")
    def test_valid_identity_reaches_offline_gate(self, gate):
        self.validate()
        gate.assert_called_once()

    @patch("agent.trusted_docker_executor.validate_admitted_worker_plan")
    def test_tampered_signature_never_reaches_gate(self, gate):
        with self.assertRaises(ValueError):
            self.validate(signature="0" * 64)
        gate.assert_not_called()

    @patch("agent.trusted_docker_executor.validate_admitted_worker_plan")
    def test_wrong_job_id_never_reaches_gate(self, gate):
        with self.assertRaises(PermissionError):
            self.validate(job_id="job2")
        gate.assert_not_called()

    @patch("agent.trusted_docker_executor.validate_admitted_worker_plan")
    def test_wrong_commit_never_reaches_gate(self, gate):
        with self.assertRaises(PermissionError):
            self.validate(expected_commit_sha="c" * 40)
        gate.assert_not_called()

    @patch("agent.trusted_docker_executor.validate_admitted_worker_plan")
    def test_wrong_manifest_never_reaches_gate(self, gate):
        with self.assertRaises(ValueError):
            self.validate(expected_manifest="c" * 64)
        gate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
