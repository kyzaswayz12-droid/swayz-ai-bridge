import tempfile
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent.job_inbox import JobInbox
from agent.test_handoff import prepare_test_handoff
from agent.ed25519_worker_envelope_v2 import sign_worker_envelope_v2
from agent.ed25519_worker_preparation_v2 import prepare_v2_worker_job
from agent.worker_journal import WorkerJournal

IMAGE = "sha256:" + "a" * 64
SHA = "b" * 40


class V2WorkerPreparationTests(unittest.TestCase):
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
        self.key = Ed25519PrivateKey.generate()
        manifest = prepare_test_handoff("job1", self.source, self.changes)
        payload = dict(version="2", job_id="job1",
                       repository="kyzaswayz12-droid/swayz-ai-bridge",
                       commit_sha=SHA, suite="python-unittest",
                       manifest_sha256=manifest.manifest_sha256, image_digest=IMAGE)
        self.raw, self.sig = sign_worker_envelope_v2(payload, self.key)

    def tearDown(self):
        self.inbox.close()
        self.temp.cleanup()

    def prepare(self, **kwargs):
        args = dict(job_id="job1", workspace=self.source, changes=self.changes,
                    observed_commit=SHA, image_digest=IMAGE,
                    approved_images=frozenset({IMAGE}), snapshot_root=str(self.snapshots),
                    journal_path=self.journal)
        args.update(kwargs)
        return prepare_v2_worker_job(self.inbox, self.raw, self.sig,
                                     self.key.public_key(), **args)

    def test_signed_snapshot_and_journal(self):
        snapshot, hashes = self.prepare()
        self.assertTrue(Path(snapshot).is_dir())
        self.assertIn("test_demo.py", hashes)
        journal = WorkerJournal(self.journal)
        self.assertEqual(journal.status("job1")[0], "admitted")
        journal.close()

    def test_commit_mismatch_rejected(self):
        with self.assertRaises(PermissionError):
            self.prepare(observed_commit="c" * 40)

    def test_unapproved_image_rejected(self):
        with self.assertRaises(PermissionError):
            self.prepare(approved_images=frozenset())

    def test_duplicate_job_rejected(self):
        self.prepare()
        with self.assertRaises(PermissionError):
            self.prepare()
