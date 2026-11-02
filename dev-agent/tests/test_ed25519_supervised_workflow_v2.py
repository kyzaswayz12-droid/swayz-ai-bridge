import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent.job_inbox import JobInbox
from agent.test_handoff import prepare_test_handoff
from agent.ed25519_worker_envelope_v2 import sign_worker_envelope_v2
from agent.ed25519_supervised_workflow_v2 import execute_v2_supervised_job
from agent.worker_journal import WorkerJournal

IMAGE = "sha256:" + "a" * 64
SHA = "b" * 40


class Ed25519SupervisedWorkflowV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.source = root / "job1"
        self.source.mkdir()
        self.changes = {"tests/test_demo.py": "import unittest\nclass Demo(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n"}
        (self.source / "tests").mkdir()
        (self.source / "tests" / "test_demo.py").write_text(self.changes["tests/test_demo.py"])
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

    def call(self, **kwargs):
        args = dict(job_id="job1", workspace=self.source, changes=self.changes,
                    observed_commit=SHA, image_digest=IMAGE,
                    approved_images=frozenset({IMAGE}), snapshot_root=str(self.snapshots),
                    journal_path=self.journal, authorised=True)
        args.update(kwargs)
        return execute_v2_supervised_job(
            self.inbox, self.raw, self.sig, self.key.public_key(), **args)

    def test_complete_mock_execution(self):
        calls = []
        def runner(argv, **kw):
            calls.append(argv)
            return SimpleNamespace(returncode=0 if len(calls) == 1 else 1,
                                   stdout="OK", stderr="" if len(calls) == 1 else
                                   "Error: No such object: swayz-test-job1")
        result = self.call(executor=runner)
        self.assertEqual(result.state, "passed")
        journal = WorkerJournal(self.journal)
        self.assertEqual(journal.status("job1")[0], "passed")
        journal.close()

    def test_disabled_rejects_without_admission(self):
        with self.assertRaises(PermissionError):
            self.call(authorised=False)
        self.assertFalse((self.snapshots / "job1").exists())

    def test_commit_mismatch_rejected(self):
        with self.assertRaises(PermissionError):
            self.call(observed_commit="c" * 40, executor=lambda *a, **kw: None)

    def test_unapproved_image_rejected(self):
        with self.assertRaises(PermissionError):
            self.call(approved_images=frozenset(), executor=lambda *a, **kw: None)
