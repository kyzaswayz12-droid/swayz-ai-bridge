"""Prepared offline request reconciliation; no server, Docker or signing calls."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from deployment import swayz_one_shot_window as window


JOB = "swayzoffline20261120a"
ROOT = "/var/lib/swayz-executor/snapshots"
SNAP = ROOT + "/" + JOB


class PreparedRequestRootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key = Path(self.tmp.name) / "key"
        self.key.write_bytes(b"test-key")
        self.key.chmod(0o600)
        self.metadata = dict(job_id=JOB, commit_sha="commit", manifest_sha256="manifest",
                             snapshot=SNAP, snapshot_root=SNAP,
                             expected_hashes={"a": "b"}, image_digest="image")
        self.request = dict(job_id=JOB, request_id=None, provider="none",
                            raw_hex="00", signature="signature",
                            expected_manifest="manifest", expected_commit_sha="commit",
                            snapshot=SNAP, snapshot_root=ROOT,
                            expected_hashes={"a": "b"}, image_digest="image", now="2026-11-21")

    def check(self):
        with patch.object(window, "protected_json", return_value=self.request), \\
             patch.object(window, "verify_manifest_job") as verify:
            verify.return_value.job_id = JOB
            verify.return_value.commit_sha = "commit"
            window.validate_prepared_request(JOB, self.metadata, str(self.key))
            verify.assert_called_once()

    def test_legacy_metadata_snapshot_root_accepted(self):
        self.check()

    def test_parent_root_metadata_accepted(self):
        self.metadata["snapshot_root"] = ROOT
        self.check()

    def test_unrelated_request_root_rejected(self):
        self.request["snapshot_root"] = "/tmp/snapshots"
        with self.assertRaises(PermissionError):
            self.check()

    def test_unrelated_metadata_root_rejected(self):
        self.metadata["snapshot_root"] = "/tmp/snapshots"
        with self.assertRaises(PermissionError):
            self.check()

    def test_modified_hashes_rejected(self):
        self.request["expected_hashes"] = {"a": "changed"}
        with self.assertRaises(PermissionError):
            self.check()


if __name__ == "__main__":
    unittest.main()
