import tempfile
import unittest
from pathlib import Path
from agent.job_inbox import JobInbox
from agent.test_jobs import TestJob
from agent.test_handoff import prepare_test_handoff
from agent.signed_handoff import sign_manifest_job
from agent.signed_worker_snapshot import stage_signed_worker_snapshot

DIGEST = "sha256:" + "a" * 64
SECRET = b"s" * 32


class SignedWorkerSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.source = root / "job1"
        self.source.mkdir()
        self.changes = {"test_demo.py": "print('test')\n"}
        (self.source / "test_demo.py").write_text(self.changes["test_demo.py"])
        self.destination = root / "snapshots" / "job1"
        self.destination.parent.mkdir()
        self.inbox = JobInbox(str(root / "inbox.db"))
        handoff = prepare_test_handoff("job1", self.source, self.changes)
        self.raw, self.signature = sign_manifest_job(
            TestJob("job1", "kyzaswayz12-droid/swayz-ai-bridge",
                    "a" * 40, "python-unittest"),
            handoff.manifest_sha256, SECRET)

    def tearDown(self):
        self.inbox.close()
        self.temp.cleanup()

    def call(self, **kwargs):
        args = dict(job_id="job1", workspace=self.source, changes=self.changes,
                    image_digest=DIGEST, snapshot_directory=self.destination)
        args.update(kwargs)
        return stage_signed_worker_snapshot(
            self.inbox, self.raw, self.signature, SECRET, **args)

    def test_valid_signed_snapshot_prepared(self):
        result = self.call()
        self.assertEqual(result.state, "snapshot_prepared")
        self.assertEqual((self.destination / "test_demo.py").read_text(), "print('test')\n")
        self.assertFalse(result.docker_executed)

    def test_tampered_source_rejected(self):
        (self.source / "test_demo.py").write_text("tampered")
        with self.assertRaises(ValueError):
            self.call()
        self.assertFalse(self.destination.exists())

    def test_duplicate_job_rejected(self):
        self.call()
        self.destination.chmod(0o700)
        self.destination.rename(self.destination.parent / "archived")
        result = self.call()
        self.assertEqual(result.state, "duplicate_rejected")

    def test_invalid_signature_rejected(self):
        with self.assertRaises(ValueError):
            stage_signed_worker_snapshot(
                self.inbox, self.raw, "0" * 64, SECRET,
                job_id="job1", workspace=self.source, changes=self.changes,
                image_digest=DIGEST, snapshot_directory=self.destination)
        self.assertFalse(self.destination.exists())
