import tempfile
import unittest
from pathlib import Path
from agent.staging_writer import stage_changes

class StagingWriterTests(unittest.TestCase):
    def test_private_stage(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"staging"
            parent.mkdir(mode=0o700)
            root=stage_changes(parent,"job_1",{"tests/test_risk.py":"assert True"})
            self.assertEqual((root/"tests/test_risk.py").read_text(),"assert True")
            self.assertEqual((root/"tests/test_risk.py").stat().st_mode & 0o777,0o600)
    def test_existing_job_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"staging"
            parent.mkdir(mode=0o700)
            stage_changes(parent,"job_1",{"a.py":"x"})
            with self.assertRaises(FileExistsError):
                stage_changes(parent,"job_1",{"a.py":"y"})
    def test_unsafe_path_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"staging"
            parent.mkdir(mode=0o700)
            with self.assertRaises(ValueError):
                stage_changes(parent,"job_1",{"../escape.py":"x"})
    def test_public_parent_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"staging"
            parent.mkdir(mode=0o700)
            parent.chmod(0o755)
            with self.assertRaises(PermissionError):
                stage_changes(parent,"job_1",{"a.py":"x"})
