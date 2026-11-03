"""No-spend, no-Docker tests for the trusted executor validation boundary."""
import tempfile
import unittest
from pathlib import Path

from agent.trusted_docker_executor import (
    execute_trusted_worker, validate_trusted_worker_plan,
)


class TrustedDockerExecutorTests(unittest.TestCase):
    def test_execution_always_disabled(self):
        with self.assertRaises(PermissionError):
            execute_trusted_worker()

    def test_unapproved_image_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PermissionError):
                validate_trusted_worker_plan(
                    job_id="job1", snapshot=d, snapshot_root=d,
                    expected_hashes={}, image_digest="sha256:" + "a" * 64,
                    approved_image_digests=frozenset(),
                )

    def test_mutable_approval_set_rejected(self):
        with self.assertRaises(PermissionError):
            validate_trusted_worker_plan(
                job_id="job1", snapshot="/missing", snapshot_root="/missing",
                expected_hashes={}, image_digest="sha256:" + "a" * 64,
                approved_image_digests={"sha256:" + "a" * 64},
            )

    def test_outside_snapshot_rejected(self):
        digest = "sha256:" + "a" * 64
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "snapshots"
            root.mkdir()
            other = Path(d) / "job1"
            other.mkdir()
            with self.assertRaises(PermissionError):
                validate_trusted_worker_plan(
                    job_id="job1", snapshot=str(other), snapshot_root=str(root),
                    expected_hashes={}, image_digest=digest,
                    approved_image_digests=frozenset({digest}),
                )


if __name__ == "__main__":
    unittest.main()
