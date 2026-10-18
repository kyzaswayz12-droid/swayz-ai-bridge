import hashlib
import tempfile
import unittest
from pathlib import Path
from agent.snapshot_reverification import verify_snapshot_before_execution


class SnapshotReverificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve() / "job1"
        self.root.mkdir()
        self.file = self.root / "test_demo.py"
        self.file.write_text("assert True\n")
        self.file.chmod(0o444)
        self.root.chmod(0o555)
        self.hashes = {"test_demo.py": hashlib.sha256(self.file.read_bytes()).hexdigest()}

    def tearDown(self):
        self.temp.cleanup()

    def test_matching_snapshot(self):
        self.assertTrue(verify_snapshot_before_execution(self.root, self.hashes))

    def test_modified_content_rejected(self):
        self.file.chmod(0o644)
        self.file.write_text("assert False\n")
        self.file.chmod(0o444)
        with self.assertRaises(PermissionError):
            verify_snapshot_before_execution(self.root, self.hashes)

    def test_extra_file_rejected(self):
        self.root.chmod(0o755)
        extra = self.root / "extra.py"
        extra.write_text("x")
        extra.chmod(0o444)
        self.root.chmod(0o555)
        with self.assertRaises(PermissionError):
            verify_snapshot_before_execution(self.root, self.hashes)

    def test_writable_file_rejected(self):
        self.file.chmod(0o644)
        with self.assertRaises(PermissionError):
            verify_snapshot_before_execution(self.root, self.hashes)

    def test_symlink_rejected(self):
        self.root.chmod(0o755)
        (self.root / "link").symlink_to(self.file)
        self.root.chmod(0o555)
        with self.assertRaises(PermissionError):
            verify_snapshot_before_execution(self.root, self.hashes)
