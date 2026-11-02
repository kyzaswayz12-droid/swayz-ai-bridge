import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from agent.job_inbox import JobInbox
from agent.test_jobs import TestJob
from agent.test_handoff import prepare_test_handoff
from agent.signed_handoff import sign_manifest_job
from agent.attested_worker_preparation import prepare_from_attested_checkout

SHA = "a" * 40
SECRET = b"s" * 32
IMAGE = "sha256:" + "b" * 64


class AttestedWorkerPreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.checkout = root / "checkout"
        self.checkout.mkdir()
        self.workspace = root / "job1"
        self.workspace.mkdir()
        self.changes = {"test_demo.py": "print('ok')\n"}
        (self.workspace / "test_demo.py").write_text(self.changes["test_demo.py"])
        self.snapshots = root / "snapshots"
        self.snapshots.mkdir()
        self.inbox = JobInbox(str(root / "inbox.db"))
        self.journal = str(root / "journal.db")
        handoff = prepare_test_handoff("job1", self.workspace, self.changes)
        self.raw, self.signature = sign_manifest_job(
            TestJob("job1", "kyzaswayz12-droid/swayz-ai-bridge",
                    SHA, "python-unittest"), handoff.manifest_sha256, SECRET)

    def tearDown(self):
        self.inbox.close()
        self.tmp.cleanup()

    def git_runner(self, argv, *, sha=SHA, dirty=False):
        if "rev-parse" in argv:
            return SimpleNamespace(returncode=0, stdout=sha + "\n")
        if "status" in argv:
            return SimpleNamespace(returncode=0, stdout="?? unexpected\n" if dirty else "")
        raise AssertionError("Unexpected Git command")

    def call(self, runner=None):
        return prepare_from_attested_checkout(
            self.inbox, self.raw, self.signature, SECRET, job_id="job1",
            checkout=str(self.checkout), workspace=self.workspace,
            changes=self.changes, image_digest=IMAGE,
            snapshot_root=str(self.snapshots), journal_path=self.journal,
            git_runner=runner or self.git_runner)

    def test_clean_checkout_prepares_job(self):
        result = self.call()
        self.assertEqual(result.state, "awaiting_trusted_worker")
        self.assertFalse(result.docker_executed)

    def test_wrong_commit_rejected_before_snapshot(self):
        with self.assertRaises(PermissionError):
            self.call(lambda argv: self.git_runner(argv, sha="c" * 40))
        self.assertFalse((self.snapshots / "job1").exists())

    def test_dirty_checkout_rejected_before_snapshot(self):
        with self.assertRaises(PermissionError):
            self.call(lambda argv: self.git_runner(argv, dirty=True))
        self.assertFalse((self.snapshots / "job1").exists())

    def test_duplicate_signed_job_rejected(self):
        self.call()
        with self.assertRaises(PermissionError):
            self.call()
