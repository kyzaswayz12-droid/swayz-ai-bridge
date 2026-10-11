import tempfile
import unittest
from pathlib import Path
from agent.staging_writer import stage_changes
from agent.staging_manifest import verify_staged_changes

class StagingManifestTests(unittest.TestCase):
    def test_matching_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"private"
            parent.mkdir(mode=0o700)
            changes={"tests/test_risk.py":"assert True"}
            root=stage_changes(parent,"job1",changes)
            manifest=verify_staged_changes(root,changes)
            self.assertEqual(manifest["tests/test_risk.py"]["bytes"],len("assert True"))
            self.assertEqual(len(manifest["tests/test_risk.py"]["sha256"]),64)
    def test_tampered_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"private"
            parent.mkdir(mode=0o700)
            changes={"a.py":"original"}
            root=stage_changes(parent,"job1",changes)
            (root/"a.py").write_text("modified")
            with self.assertRaises(ValueError):
                verify_staged_changes(root,changes)
    def test_extra_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"private"
            parent.mkdir(mode=0o700)
            changes={"a.py":"x"}
            root=stage_changes(parent,"job1",changes)
            (root/"extra.py").write_text("y")
            with self.assertRaises(ValueError):
                verify_staged_changes(root,changes)
