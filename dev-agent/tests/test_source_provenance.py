import tempfile
import unittest
from pathlib import Path
from agent.source_provenance import verify_checkout_provenance

SHA = "a" * 40


class SourceProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / "checkout"
        self.workspace.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def check(self, **overrides):
        args = dict(expected_commit=SHA, observed_commit=SHA,
                    workspace=str(self.workspace), approved_root=str(self.root))
        args.update(overrides)
        return verify_checkout_provenance(**args)

    def test_matching_commit_inside_root(self):
        self.assertTrue(self.check())

    def test_commit_mismatch_rejected(self):
        with self.assertRaises(PermissionError):
            self.check(observed_commit="b" * 40)

    def test_invalid_commit_rejected(self):
        with self.assertRaises(ValueError):
            self.check(expected_commit="main")

    def test_workspace_outside_root_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(PermissionError):
                self.check(workspace=other)

    def test_symlink_workspace_rejected(self):
        link = self.root / "link"
        link.symlink_to(self.workspace, target_is_directory=True)
        with self.assertRaises(PermissionError):
            self.check(workspace=str(link))
