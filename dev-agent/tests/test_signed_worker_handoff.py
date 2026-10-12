import tempfile
import unittest
from pathlib import Path
from agent.job_inbox import JobInbox
from agent.test_jobs import TestJob
from agent.test_handoff import prepare_test_handoff
from agent.signed_handoff import sign_manifest_job
from agent.signed_worker_handoff import authorise_and_plan

DIGEST = "sha256:" + "a" * 64
SECRET = b"s" * 32
SHA = "a" * 40


class SignedWorkerHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.workspace = root / "job1"
        self.workspace.mkdir()
        self.changes = {"sample.py": "print('hello')\n"}
        (self.workspace / "sample.py").write_text(self.changes["sample.py"])
        self.inbox = JobInbox(str(root / "inbox.db"))
        manifest = prepare_test_handoff("job1", self.workspace, self.changes)
        self.raw, self.signature = sign_manifest_job(
            TestJob("job1", "kyzaswayz12-droid/swayz-ai-bridge",
                    SHA, "python-unittest"), manifest.manifest_sha256, SECRET)

    def tearDown(self):
        self.inbox.close()
        self.temp.cleanup()

    def plan(self, **overrides):
        args = dict(job_id="job1", workspace=self.workspace,
                    changes=self.changes, image_digest=DIGEST)
        args.update(overrides)
        return authorise_and_plan(self.inbox, self.raw, self.signature, SECRET, **args)

    def test_valid_signed_job_plans_without_docker(self):
        result = self.plan()
        self.assertEqual(result.state, "accepted_for_offline_planning")
        self.assertFalse(result.docker_executed)
        self.assertIsNotNone(result.lifecycle)

    def test_duplicate_signed_job_rejected(self):
        self.plan()
        result = self.plan()
        self.assertEqual(result.state, "duplicate_rejected")
        self.assertIsNone(result.lifecycle)

    def test_tampered_signature_rejected(self):
        with self.assertRaises(ValueError):
            authorise_and_plan(self.inbox, self.raw, "0" * 64, SECRET,
                               job_id="job1", workspace=self.workspace,
                               changes=self.changes, image_digest=DIGEST)

    def test_changed_staged_content_rejected(self):
        (self.workspace / "sample.py").write_text("tampered")
        with self.assertRaises(ValueError):
            self.plan()
