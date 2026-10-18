import tempfile
import unittest
from pathlib import Path
from agent.job_inbox import JobInbox
from agent.test_jobs import TestJob
from agent.test_handoff import prepare_test_handoff
from agent.signed_handoff import sign_manifest_job
from agent.integrated_worker_preparation import prepare_integrated_job
from agent.worker_journal import WorkerJournal

SECRET = b"s" * 32
DIGEST = "sha256:" + "a" * 64


class IntegratedWorkerPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.source = root / "job1"
        self.source.mkdir()
        self.changes = {"test_demo.py": "print('ok')\n"}
        (self.source / "test_demo.py").write_text(self.changes["test_demo.py"])
        self.snapshots = root / "snapshots"
        self.snapshots.mkdir()
        self.journal_path = str(root / "journal.db")
        self.inbox = JobInbox(str(root / "inbox.db"))
        handoff = prepare_test_handoff("job1", self.source, self.changes)
        self.raw, self.signature = sign_manifest_job(
            TestJob("job1", "kyzaswayz12-droid/swayz-ai-bridge",
                    "a" * 40, "python-unittest"),
            handoff.manifest_sha256, SECRET)

    def tearDown(self):
        self.inbox.close()
        self.temp.cleanup()

    def call(self, signature=None):
        return prepare_integrated_job(
            self.inbox, self.raw, signature or self.signature, SECRET,
            job_id="job1", workspace=self.source, changes=self.changes,
            image_digest=DIGEST, snapshot_root=str(self.snapshots),
            journal_path=self.journal_path)

    def test_complete_offline_preparation(self):
        result = self.call()
        self.assertEqual(result.state, "awaiting_trusted_worker")
        self.assertFalse(result.docker_executed)
        self.assertIn(f"type=bind,src={self.snapshots / 'job1'},dst=/work,readonly",
                      result.docker_argv)
        journal = WorkerJournal(self.journal_path)
        self.assertEqual(journal.status("job1")[0], "admitted")
        journal.close()

    def test_invalid_signature_rejected(self):
        with self.assertRaises(ValueError):
            self.call(signature="0" * 64)
        self.assertFalse((self.snapshots / "job1").exists())

    def test_tampered_source_rejected(self):
        (self.source / "test_demo.py").write_text("tampered")
        with self.assertRaises(ValueError):
            self.call()

    def test_duplicate_job_rejected(self):
        self.call()
        with self.assertRaises(PermissionError):
            self.call()
