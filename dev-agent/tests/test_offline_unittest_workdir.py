"""Regression: approved snapshot contains dev-agent/tests, not root/tests."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from agent.worker_lifecycle import plan_worker_lifecycle

class OfflineUnittestWorkdirTests(unittest.TestCase):
    def test_workdir_matches_snapshot_layout(self):
        with TemporaryDirectory() as parent:
            root = Path(parent) / "job123"
            (root / "dev-agent" / "tests").mkdir(parents=True)
            plan = plan_worker_lifecycle("job123", "sha256:" + "a"*64, workspace=str(root))
            self.assertIn(("--workdir", "/home"), tuple(zip(plan.run_argv, plan.run_argv[1:])))
            self.assertEqual(plan.run_argv[-9:], ("python", "-m", "unittest", "discover", "-s", "dev-agent/tests", "-t", "dev-agent", "-v"))

if __name__ == "__main__":
    unittest.main()
