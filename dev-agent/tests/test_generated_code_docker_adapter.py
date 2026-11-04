import tempfile
import unittest
from pathlib import Path
from agent.change_plan import ApprovedPlan, Change
from agent.generated_code_docker_adapter import run_generated_code_tests


class GeneratedCodeDockerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.staging = root / "staging"
        self.snapshots = root / "snapshots"
        self.staging.mkdir()
        self.snapshots.mkdir()
        self.calls = []

    def run(self, plan, executor=None):
        def trusted(**kwargs):
            self.calls.append(kwargs)
            return {"state":"passed","cleanup_verified":True}
        return run_generated_code_tests(
            job_id="job1", plan=plan,
            staging_root=str(self.staging), snapshot_root=str(self.snapshots),
            require_running=lambda: None,
            trusted_execute=executor or trusted)

    def plan(self, changes):
        return ApprovedPlan("a"*40, "b"*64, "agent/test", tuple(
            Change(path, content) for path, content in changes.items()))

    def test_generated_test_snapshot_is_verified_and_submitted(self):
        result = self.run(self.plan({"tests/test_fix.py":
            "import unittest\nclass TestFix(unittest.TestCase):\n"
            " def test_ok(self): self.assertEqual(1, 1)\n"}))
        self.assertEqual(result["state"],"passed")
        self.assertEqual(len(self.calls),1)
        self.assertTrue((self.snapshots/"job1/tests/test_fix.py").exists())
        self.assertEqual((self.snapshots/"job1").stat().st_mode & 0o222,0)

    def test_no_test_rejected_without_execution(self):
        with self.assertRaises(PermissionError):
            self.run(self.plan({"docs/README.md":"not tested"}))
        self.assertEqual(self.calls,[])

    def test_source_changes_rejected_until_checkout_is_verified(self):
        with self.assertRaises(PermissionError):
            self.run(self.plan({"agent/worker.py":"x=1",
                "tests/test_worker.py":"assert True"}))
        self.assertEqual(self.calls,[])

    def test_cleanup_failure_blocks(self):
        result=self.run(self.plan({"tests/test_fix.py":"assert True"}),
            executor=lambda **kwargs:{"state":"passed","cleanup_verified":False})
        self.assertEqual(result["state"],"blocked")

    def test_stop_rejects_before_staging(self):
        with self.assertRaises(PermissionError):
            run_generated_code_tests(
                job_id="job1",plan=self.plan({"tests/test_fix.py":"assert True"}),
                staging_root=str(self.staging),snapshot_root=str(self.snapshots),
                require_running=lambda: (_ for _ in ()).throw(PermissionError("stop")),
                trusted_execute=lambda **kwargs:None)
        self.assertFalse((self.staging/"job1").exists())
