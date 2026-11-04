"""Positive and adversarial tests of the offline trusted worker plan boundary.

These tests do not invoke Docker, network services or paid APIs.
"""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from agent.trusted_docker_executor import validate_trusted_worker_plan

DIGEST = "sha256:" + "a" * 64


class TrustedExecutorManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "snapshots"
        self.root.mkdir()
        self.snapshot = self.root / "job1"
        self.snapshot.mkdir()
        self.file = self.snapshot / "sample.txt"
        self.file.write_bytes(b"known-good")
        self.file.chmod(0o444)
        self.snapshot.chmod(0o555)
        self.hashes = {"sample.txt": hashlib.sha256(b"known-good").hexdigest()}

    def tearDown(self):
        self.snapshot.chmod(0o755)
        self.file.chmod(0o644)

    def validate(self, **overrides):
        args = dict(
            job_id="job1", snapshot=str(self.snapshot),
            snapshot_root=str(self.root), expected_hashes=self.hashes,
            image_digest=DIGEST, approved_image_digests=frozenset({DIGEST}),
        )
        args.update(overrides)
        return validate_trusted_worker_plan(**args)

    def test_valid_plan_is_nonexecuting_and_restricted(self):
        result = self.validate()
        argv = result.lifecycle.run_argv
        self.assertFalse(result.lifecycle.executes)
        for flag, value in (
            ("--network", "none"), ("--cap-drop", "ALL"),
            ("--user", "65534:65534"),
        ):
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertIn("--read-only", argv)
        self.assertIn("--rm", argv)
        self.assertIn("--security-opt", argv)
        self.assertIn("type=bind,src=" + str(self.snapshot) + ",dst=/work,readonly", argv)

    def test_tampered_snapshot_rejected(self):
        self.file.chmod(0o644)
        self.file.write_bytes(b"tampered")
        self.file.chmod(0o444)
        with self.assertRaises(PermissionError):
            self.validate()

    def test_writable_snapshot_rejected(self):
        self.snapshot.chmod(0o755)
        with self.assertRaises(PermissionError):
            self.validate()

    def test_symlink_in_snapshot_rejected(self):
        link = self.snapshot / "link"
        self.snapshot.chmod(0o755)
        link.symlink_to(self.file)
        self.snapshot.chmod(0o555)
        with self.assertRaises(PermissionError):
            self.validate()

    def test_invalid_timeout_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(timeout_seconds=301)

    def test_missing_manifest_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(expected_hashes={})


if __name__ == "__main__":
    unittest.main()
