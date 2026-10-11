import tempfile
import unittest
from pathlib import Path
from agent.coding_job import prepare_coding_job

class CodingJobTests(unittest.TestCase):
    def test_verified_staging_job(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"private"
            parent.mkdir(mode=0o700)
            result=prepare_coding_job(parent,"job1",{"tests/test_risk.py":"assert True"})
            self.assertEqual(result.state,"staged_verified")
            self.assertIn("tests/test_risk.py",result.manifest)
            self.assertTrue((Path(result.workspace)/"tests/test_risk.py").is_file())
    def test_unsafe_changes_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"private"
            parent.mkdir(mode=0o700)
            with self.assertRaises(ValueError):
                prepare_coding_job(parent,"job1",{"../escape.py":"x"})
            self.assertFalse((parent/"job1").exists())
