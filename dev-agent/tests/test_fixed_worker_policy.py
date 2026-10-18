import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from agent.worker_lifecycle import plan_worker_lifecycle
from agent.fixed_worker_policy import verify_fixed_worker_plan

IMAGE = "sha256:" + "a" * 64


class FixedWorkerPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.snapshot = Path(self.temp.name).resolve() / "job1"
        self.snapshot.mkdir()
        self.plan = plan_worker_lifecycle("job1", IMAGE, workspace=str(self.snapshot))

    def tearDown(self):
        self.temp.cleanup()

    def verify(self, plan=None, approved=None):
        return verify_fixed_worker_plan(
            self.plan if plan is None else plan, job_id="job1",
            image_digest=IMAGE, snapshot=str(self.snapshot),
            approved_image_digests=frozenset({IMAGE}) if approved is None else approved)

    def test_exact_plan_accepted(self):
        self.assertTrue(self.verify())

    def test_network_enabled_plan_rejected(self):
        args = list(self.plan.run_argv)
        args[args.index("none")] = "bridge"
        with self.assertRaises(PermissionError):
            self.verify(plan=replace(self.plan, run_argv=tuple(args)))

    def test_privileged_flag_rejected(self):
        with self.assertRaises(PermissionError):
            self.verify(plan=replace(self.plan, run_argv=self.plan.run_argv + ("--privileged",)))

    def test_unapproved_image_rejected(self):
        with self.assertRaises(PermissionError):
            self.verify(approved=frozenset())

    def test_modified_cleanup_command_rejected(self):
        with self.assertRaises(PermissionError):
            self.verify(plan=replace(self.plan, kill_argv=("docker", "kill", "other")))
