import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent.protected_admission_loader import load_protected_job

class ProtectedAdmissionLoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.root.chmod(0o700)
        self.doc={key:"value" for key in (
            "job_id","commit_sha","proposal_sha256","manifest_sha256",
            "snapshot","snapshot_root","image_digest","queue_db","job_db",
            "journal_db","stop_db","signing_key_file","request_directory")}
        self.doc["job_id"]="job1"
        self.doc["expected_hashes"]={"tests/test.py":"a"*64}
        self.doc["approved_images"]=["sha256:"+"b"*64]
        self.path=self.root/"job1.json"
        self.write()
    def write(self):
        self.path.write_text(json.dumps(self.doc))
        self.path.chmod(0o600)
    def load(self, job_id="job1"):
        original_stat = Path.stat
        original_fstat = os.fstat
        def root_owned(path, *args, **kwargs):
            st = original_stat(path, *args, **kwargs)
            if str(path) == str(self.root):
                values = list(st)
                values[4] = 0
                return os.stat_result(values)
            return st
        with patch("agent.protected_admission_loader.os.geteuid", return_value=0), \
             patch("pathlib.Path.stat", root_owned), \
             patch("agent.protected_admission_loader.os.fstat", side_effect=lambda fd: self._root_fstat(original_fstat(fd))):
            return load_protected_job(job_id, metadata_directory=str(self.root))
    @staticmethod
    def _root_fstat(st):
        values = list(st)
        values[4] = 0
        return os.stat_result(values)

    def test_protected_metadata_loads(self):
        self.assertEqual(self.load()["approved_images"],frozenset(self.doc["approved_images"]))
    def test_path_traversal_rejected(self):
        with self.assertRaises(PermissionError):
            self.load("../job1")
    def test_world_readable_file_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaises(PermissionError):
            self.load()
    def test_untrusted_extra_field_rejected(self):
        self.doc["override"]="/tmp"
        self.write()
        with self.assertRaises(PermissionError):
            self.load()
    def test_nonroot_rejected(self):
        with patch("agent.protected_admission_loader.os.geteuid",return_value=995):
            with self.assertRaises(PermissionError):
                load_protected_job("job1",metadata_directory=str(self.root))
    def test_symlink_rejected(self):
        self.path.unlink()
        (self.root/"target").write_text("{}")
        self.path.symlink_to(self.root/"target")
        with self.assertRaises(OSError):
            self.load()
