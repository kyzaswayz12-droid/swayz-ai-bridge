import tempfile
import unittest
from pathlib import Path
from agent.job_inbox import JobInbox
from agent.test_jobs import TestJob
from agent.test_handoff import prepare_test_handoff
from agent.signed_handoff import sign_manifest_job
from agent.integrated_worker_preparation import prepare_integrated_job

SECRET = b"s" * 32
DIGEST = "sha256:" + "a" * 64
SHA = "a" * 40


class IntegratedIdentityBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.source = root / "job1"
        self.source.mkdir()
        self.changes = {"test_demo.py": "print('ok')\n"}
        (self.source / "test_demo.py").write_text(self.changes["test_demo.py"])
        self.snapshots = root / "snapshots"
        self.snapshots.mkdir()
        self.journal = str(root / "journal.db")
        self.inbox = JobInbox(str(root / "inbox.db"))
        handoff = prepare_test_handoff("job1", self.source, self.changes)
        self.raw, self.signature = sign_manifest_job(
            TestJob("job1", "kyzaswayz12-droid/swayz-ai-bridge",
                    SHA, "python-unittest"), handoff.manifest_sha256, SECRET)

    def tearDown(self):
        self.inbox.close()
        self.temp.cleanup()

    def call(self, observed):
        return prepare_integrated_job(
            self.inbox, self.raw, self.signature, SECRET,
            job_id="job1", workspace=self.source, changes=self.changes,
            image_digest=DIGEST, snapshot_root=str(self.snapshots),
            journal_path=self.journal, observed_commit_sha=observed)

    def test_matching_observed_commit(self):
        self.assertEqual(self.call(SHA).state, "awaiting_trusted_worker")

    def test_wrong_commit_rejected_before_snapshot(self):
        with self.assertRaises(PermissionError):
            self.call("b" * 40)
        self.assertFalse((self.snapshots / "job1").exists())

    def test_invalid_commit_rejected(self):
        with self.assertRaises(PermissionError):
            self.call("main")
        self.assertFalse((self.snapshots / "job1").exists())
