import tempfile
import unittest
from pathlib import Path
from agent.snapshot_execution_plan import plan_snapshot_execution

DIGEST = "sha256:" + "a" * 64


class SnapshotExecutionPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.snapshot_root = self.root / "snapshots"
        self.snapshot_root.mkdir()
        self.snapshot = self.snapshot_root / "job1"
        self.snapshot.mkdir()
        self.snapshot.chmod(0o555)

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, **overrides):
        args = dict(job_id="job1", snapshot=str(self.snapshot),
                    snapshot_root=str(self.snapshot_root), image_digest=DIGEST)
        args.update(overrides)
        return plan_snapshot_execution(**args)

    def test_mounts_only_snapshot(self):
        plan = self.plan()
        self.assertEqual(plan.state, "awaiting_trusted_worker")
        self.assertIn(f"type=bind,src={self.snapshot},dst=/work,readonly",
                      plan.lifecycle.run_argv)
        self.assertFalse(plan.docker_executed)

    def test_writable_snapshot_rejected(self):
        self.snapshot.chmod(0o755)
        with self.assertRaises(PermissionError):
            self.plan()

    def test_outside_root_rejected(self):
        outside = self.root / "job1"
        outside.mkdir()
        outside.chmod(0o555)
        with self.assertRaises(PermissionError):
            self.plan(snapshot=str(outside))

    def test_symlink_snapshot_rejected(self):
        link = self.snapshot_root / "link"
        link.symlink_to(self.snapshot, target_is_directory=True)
        with self.assertRaises(PermissionError):
            self.plan(snapshot=str(link), job_id="link")
