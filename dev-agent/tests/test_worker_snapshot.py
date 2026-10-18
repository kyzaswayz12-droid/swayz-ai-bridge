import hashlib
import tempfile
import unittest
from pathlib import Path
from agent.worker_snapshot import prepare_readonly_snapshot


class WorkerSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "tests").mkdir()
        (self.source / "tests" / "test_demo.py").write_text("assert 1 == 1\n")
        self.destination = self.root / "snapshot"
        self.manifest = {"tests/test_demo.py": hashlib.sha256(
            (self.source / "tests" / "test_demo.py").read_bytes()).hexdigest()}

    def tearDown(self):
        self.temp.cleanup()

    def test_manifest_bound_snapshot(self):
        result = prepare_readonly_snapshot(self.source, self.destination,
                                            expected_files=self.manifest)
        self.assertEqual((result / "tests" / "test_demo.py").read_text(), "assert 1 == 1\n")
        self.assertEqual(result.stat().st_mode & 0o777, 0o555)
        self.assertEqual((result / "tests" / "test_demo.py").stat().st_mode & 0o777, 0o444)

    def test_modified_source_rejected(self):
        (self.source / "tests" / "test_demo.py").write_text("tampered")
        with self.assertRaises(PermissionError):
            prepare_readonly_snapshot(self.source, self.destination,
                                      expected_files=self.manifest)

    def test_extra_source_file_rejected(self):
        (self.source / "unexpected.py").write_text("x")
        with self.assertRaises(PermissionError):
            prepare_readonly_snapshot(self.source, self.destination,
                                      expected_files=self.manifest)

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            prepare_readonly_snapshot(self.source, self.destination,
                                      expected_files={"../escape": "a"*64})

    def test_existing_destination_rejected(self):
        self.destination.mkdir()
        with self.assertRaises(PermissionError):
            prepare_readonly_snapshot(self.source, self.destination,
                                      expected_files=self.manifest)
