import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from agent.worker_journal import WorkerJournal
from agent.supervised_docker_executor import execute_supervised_job

IMAGE = "sha256:" + "a" * 64


class SupervisedDockerExecutorTests(unittest.TestCase):
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
        store = WorkerJournal(self.journal)
        store.record_admission("job1")
        store.close()
        self.args = dict(job_id="job1", snapshot=str(self.snapshot),
                         snapshot_root=str(self.snapshots), expected_hashes=self.hashes,
                         image_digest=IMAGE, approved_image_digests=frozenset({IMAGE}),
                         journal_path=self.journal)

    def tearDown(self):
        self.temp.cleanup()

    def test_disabled_by_default(self):
        with self.assertRaises(PermissionError):
            execute_supervised_job(**self.args)

    def test_success_persisted(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0 if len(calls) == 1 else 1,
                                   stdout="OK", stderr="")
        result = execute_supervised_job(**self.args, authorised=True, executor=runner)
        self.assertEqual(result.state, "passed")
        self.assertTrue(result.cleanup_verified)

    def test_failed_tests_recorded(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=2 if len(calls) == 1 else 1,
                                   stdout="", stderr="failed")
        result = execute_supervised_job(**self.args, authorised=True, executor=runner)
        self.assertEqual(result.state, "failed")

    def test_timeout_blocks_and_kills(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            if len(calls) == 1:
                raise subprocess.TimeoutExpired(argv, 120)
            return SimpleNamespace(returncode=0 if len(calls) == 2 else 1,
                                   stdout="", stderr="")
        result = execute_supervised_job(**self.args, authorised=True, executor=runner)
        self.assertEqual(result.state, "blocked")
        self.assertTrue(result.cleanup_verified)

    def test_unapproved_image_refused(self):
        with self.assertRaises(PermissionError):
            execute_supervised_job(**{**self.args, "approved_image_digests": frozenset()},
                                   authorised=True, executor=lambda *a, **k: None)
