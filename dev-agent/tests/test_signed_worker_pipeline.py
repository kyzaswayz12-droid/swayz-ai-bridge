import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from agent.job_inbox import JobInbox
from agent.test_jobs import TestJob
from agent.test_handoff import prepare_test_handoff
from agent.signed_handoff import sign_manifest_job
from agent.signed_worker_pipeline import simulate_signed_worker_pipeline
from agent.worker_journal import WorkerJournal

DIGEST = "sha256:" + "a" * 64
SECRET = b"s" * 32


class SignedWorkerPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.workspace = root / "job1"
        self.workspace.mkdir()
        self.changes = {"sample.py": "print('hello')\n"}
        (self.workspace / "sample.py").write_text(self.changes["sample.py"])
        self.inbox = JobInbox(str(root / "inbox.db"))
        self.journal = str(root / "journal.db")
        manifest = prepare_test_handoff("job1", self.workspace, self.changes)
        self.raw, self.signature = sign_manifest_job(
            TestJob("job1", "kyzaswayz12-droid/swayz-ai-bridge",
                    "a" * 40, "python-unittest"),
            manifest.manifest_sha256, SECRET)

    def tearDown(self):
        self.inbox.close()
        self.temp.cleanup()

    def call(self, runner):
        return simulate_signed_worker_pipeline(
            self.inbox, self.raw, self.signature, SECRET,
            job_id="job1", workspace=self.workspace,
            changes=self.changes, image_digest=DIGEST,
            journal_path=self.journal, runner=runner)

    def test_success_recorded(self):
        result = self.call(lambda argv, **kw: SimpleNamespace(
            returncode=0, stdout="OK", stderr=""))
        self.assertEqual(result.state, "passed")
        journal = WorkerJournal(self.journal)
        self.assertEqual(journal.status("job1")[0], "passed")
        journal.close()

    def test_failed_test_recorded(self):
        result = self.call(lambda argv, **kw: SimpleNamespace(
            returncode=1, stdout="", stderr="failed"))
        self.assertEqual(result.state, "failed")

    def test_duplicate_rejected(self):
        runner = lambda argv, **kw: SimpleNamespace(returncode=0, stdout="", stderr="")
        self.call(runner)
        self.assertEqual(self.call(runner).state, "duplicate_rejected")

    def test_real_runner_rejected(self):
        with self.assertRaises(PermissionError):
            self.call(subprocess.run)
