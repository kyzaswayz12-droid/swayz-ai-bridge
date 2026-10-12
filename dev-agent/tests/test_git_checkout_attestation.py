import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from agent.git_checkout_attestation import attest_git_checkout

SHA = "a" * 40


class GitCheckoutAttestationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def runner(self, commands, *, observed=SHA, dirty=False):
        if "rev-parse" in commands:
            return SimpleNamespace(returncode=0, stdout=observed + "\n")
        if "status" in commands:
            return SimpleNamespace(returncode=0, stdout="?? untracked\n" if dirty else "")
        raise AssertionError("Unexpected command")

    def test_clean_matching_checkout(self):
        self.assertEqual(attest_git_checkout(self.root, SHA, runner=self.runner), SHA)

    def test_wrong_commit_rejected(self):
        with self.assertRaises(PermissionError):
            attest_git_checkout(self.root, SHA, runner=lambda args:
                self.runner(args, observed="b" * 40))

    def test_dirty_checkout_rejected(self):
        with self.assertRaises(PermissionError):
            attest_git_checkout(self.root, SHA, runner=lambda args:
                self.runner(args, dirty=True))

    def test_invalid_expected_sha_rejected(self):
        with self.assertRaises(ValueError):
            attest_git_checkout(self.root, "main", runner=self.runner)

    def test_symlink_checkout_rejected(self):
        link = self.root / "link"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(PermissionError):
            attest_git_checkout(link, SHA, runner=self.runner)
