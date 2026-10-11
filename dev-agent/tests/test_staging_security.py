import tempfile
import unittest
from pathlib import Path
from agent.staging_security import verify_private_parent

class StagingSecurityTests(unittest.TestCase):
    def test_private_parent_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"private"
            p.mkdir(mode=0o700)
            self.assertEqual(verify_private_parent(p),p)
    def test_symlink_parent_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"private"
            p.mkdir(mode=0o700)
            link=Path(d)/"alias"
            link.symlink_to(p,target_is_directory=True)
            with self.assertRaises(PermissionError):
                verify_private_parent(link)
    def test_public_parent_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"public"
            p.mkdir(mode=0o755)
            with self.assertRaises(PermissionError):
                verify_private_parent(p)
