import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from agent.job_inbox import JobInbox
from agent.test_jobs import TestJob
from agent.test_handoff import prepare_test_handoff
from agent.signed_handoff import sign_manifest_job
from agent.signed_supervised_workflow import run_signed_supervised_job
from agent.worker_journal import WorkerJournal

SHA = "a" * 40
IMAGE = "sha256:" + "b" * 64
SECRET = b"s" * 32


class SignedSupervisedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.checkout = root / "checkout"
        self.checkout.mkdir()
        self.workspace = root / "job1"
        self.workspace.mkdir()
        self.changes = {"tests/test_demo.py": "import unittest\nclass Demo(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n"}
        (self.workspace / "tests").mkdir()
        (self.workspace / "tests" / "test_demo.py").write_text(self.changes["tests/test_demo.py"])
        self.snapshots = root / "snapshots"
        self.snapshots.mkdir()
        self.journal = str(root / "journal.db")
        self.inbox = JobInbox(str(root / "inbox.db"))
        handoff = prepare_test_handoff("job1", self.workspace, self.changes)
        self.raw, self.signature = sign_manifest_job(
            TestJob("job1", "kyzaswayz12-droid/swayz-ai-bridge",
                    SHA, "python-unittest"), handoff.manifest_sha256, SECRET)

    def tearDown(self):
        self.inbox.close()
        self.tmp.cleanup()

    def git_runner(self, argv):
        return SimpleNamespace(returncode=0, stdout=SHA + "\n" if "rev-parse" in argv else "")

    def call(self, *, authorised=False, signature=None, executor=None):
        return run_signed_supervised_job(
            self.inbox, self.raw, signature or self.signature, SECRET,
            job_id="job1", checkout=str(self.checkout),
            workspace=self.workspace, changes=self.changes,
            image_digest=IMAGE, approved_image_digests=frozenset({IMAGE}),
            snapshot_root=str(self.snapshots), journal_path=self.journal,
            git_runner=self.git_runner, authorised=authorised, executor=executor)

    def test_disabled_by_default(self):
        with self.assertRaises(PermissionError):
            self.call()
        self.assertFalse((self.snapshots / "job1").exists())

    def test_mock_signed_job_to_journal(self):
        calls = []
        def executor(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0 if len(calls) == 1 else 1,
                                   stdout="OK", stderr="" if len(calls) == 1 else
                                   "Error: No such object: swayz-test-job1")
        result = self.call(authorised=True, executor=executor)
        self.assertEqual(result.state, "passed")
        journal = WorkerJournal(self.journal)
        self.assertEqual(journal.status("job1")[0], "passed")
        journal.close()

    def test_invalid_signature_rejected(self):
        with self.assertRaises(ValueError):
            self.call(authorised=True, signature="0" * 64,
                      executor=lambda *a, **k: None)
        self.assertFalse((self.snapshots / "job1").exists())
