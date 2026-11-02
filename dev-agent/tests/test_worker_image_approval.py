import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from agent.worker_journal import WorkerJournal
from agent.trusted_worker_service import simulate_worker_service

IMAGE = "sha256:" + "a" * 64


class WorkerImageApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.snapshots = root / "snapshots"
        self.snapshots.mkdir()
        self.snapshot = self.snapshots / "job1"
        self.snapshot.mkdir()
        file = self.snapshot / "test_demo.py"
        file.write_text("assert True\n")
        file.chmod(0o444)
        self.snapshot.chmod(0o555)
        self.hashes = {"test_demo.py": hashlib.sha256(file.read_bytes()).hexdigest()}
        self.journal = str(root / "journal.db")
        j = WorkerJournal(self.journal)
        j.record_admission("job1")
        j.close()

    def tearDown(self):
        self.temp.cleanup()

    def test_unapproved_image_rejected_without_runner_call(self):
        calls = []
        def runner(argv, **kw):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        with self.assertRaises(PermissionError):
            simulate_worker_service(
                job_id="job1", snapshot=str(self.snapshot),
                snapshot_root=str(self.snapshots), expected_hashes=self.hashes,
                image_digest=IMAGE, journal_path=self.journal, runner=runner,
                approved_image_digests=frozenset())
        self.assertEqual(calls, [])

    def test_missing_allowlist_rejected(self):
        with self.assertRaises(PermissionError):
            simulate_worker_service(
                job_id="job1", snapshot=str(self.snapshot),
                snapshot_root=str(self.snapshots), expected_hashes=self.hashes,
                image_digest=IMAGE, journal_path=self.journal,
                runner=lambda argv, **kw: SimpleNamespace(returncode=0, stdout="", stderr=""))
