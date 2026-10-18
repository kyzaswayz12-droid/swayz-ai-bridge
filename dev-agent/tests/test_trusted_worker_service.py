import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from agent.worker_journal import WorkerJournal
from agent.trusted_worker_service import simulate_worker_service

IMAGE = "sha256:" + "a" * 64


class TrustedWorkerServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.snapshots = root / "snapshots"
        self.snapshots.mkdir()
        self.snapshot = self.snapshots / "job1"
        self.snapshot.mkdir()
        self.file = self.snapshot / "test_demo.py"
        self.file.write_text("assert True\n")
        self.file.chmod(0o444)
        self.snapshot.chmod(0o555)
        self.hashes = {"test_demo.py": hashlib.sha256(self.file.read_bytes()).hexdigest()}
        self.journal_path = str(root / "journal.db")
        journal = WorkerJournal(self.journal_path)
        journal.record_admission("job1")
        journal.close()

    def tearDown(self):
        self.temp.cleanup()

    def call(self, runner, **overrides):
        args = dict(job_id="job1", snapshot=str(self.snapshot),
                    snapshot_root=str(self.snapshots),
                    expected_hashes=self.hashes, image_digest=IMAGE,
                    journal_path=self.journal_path, runner=runner,
                    approved_image_digests=frozenset({IMAGE}))
        args.update(overrides)
        return simulate_worker_service(**args)

    def test_mock_success_persisted(self):
        state = self.call(lambda argv, **kw: SimpleNamespace(
            returncode=0, stdout="OK", stderr=""))
        self.assertEqual(state, "passed")
        journal = WorkerJournal(self.journal_path)
        self.assertEqual(journal.status("job1")[0], "passed")
        journal.close()

    def test_mock_failure_persisted(self):
        state = self.call(lambda argv, **kw: SimpleNamespace(
            returncode=1, stdout="", stderr="failed"))
        self.assertEqual(state, "failed")

    def test_tampered_snapshot_blocks_execution(self):
        self.file.chmod(0o644)
        self.file.write_text("tampered")
        self.file.chmod(0o444)
        calls = []
        def runner(argv, **kw):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        with self.assertRaises(PermissionError):
            self.call(runner)
        self.assertEqual(calls, [])

    def test_missing_admission_rejected(self):
        with self.assertRaises(PermissionError):
            self.call(lambda argv, **kw: SimpleNamespace(returncode=0, stdout="", stderr=""),
                      job_id="missing")
