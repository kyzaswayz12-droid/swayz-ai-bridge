import tempfile
import unittest
from pathlib import Path
from agent.worker_lifecycle import plan_worker_lifecycle

DIGEST = "sha256:" + "a" * 64


class WorkerWorkspaceMountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.work = self.root / "job1"
        self.work.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_readonly_mount_and_workdir(self):
        plan = plan_worker_lifecycle("job1", DIGEST, workspace=str(self.work))
        args = plan.run_argv
        self.assertIn(f"type=bind,src={self.work},dst=/work,readonly", args)
        self.assertIn("--workdir", args)
        self.assertEqual(args[args.index("--workdir")+1], "/work")
        self.assertIn("--network", args)
        self.assertEqual(args[args.index("--network")+1], "none")

    def test_mismatched_job_workspace_rejected(self):
        with self.assertRaises(PermissionError):
            plan_worker_lifecycle("other", DIGEST, workspace=str(self.work))

    def test_symlink_inside_workspace_rejected(self):
        (self.work / "link").symlink_to(self.root)
        with self.assertRaises(PermissionError):
            plan_worker_lifecycle("job1", DIGEST, workspace=str(self.work))

    def test_relative_workspace_rejected(self):
        with self.assertRaises(PermissionError):
            plan_worker_lifecycle("job1", DIGEST, workspace="job1")
