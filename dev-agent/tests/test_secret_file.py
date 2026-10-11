import os
import tempfile
import unittest
from pathlib import Path
from agent.secret_file import load_provider_keys

class SecretFileTests(unittest.TestCase):
    def test_private_file_loads_without_echoing_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"providers.env"
            p.write_text("OPENAI_API_KEY=example-openai\nANTHROPIC_API_KEY=example-anthropic\n")
            p.chmod(0o600)
            self.assertEqual(load_provider_keys(p)["OPENAI_API_KEY"],"example-openai")

    def test_public_permissions_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"providers.env"
            p.write_text("OPENAI_API_KEY=a\nANTHROPIC_API_KEY=b\n")
            p.chmod(0o644)
            with self.assertRaises(PermissionError):
                load_provider_keys(p)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"providers.env"
            p.write_text("OPENAI_API_KEY=a\nANTHROPIC_API_KEY=b\n")
            p.chmod(0o600)
            link=Path(folder)/"alias.env"
            link.symlink_to(p)
            with self.assertRaises(ValueError):
                load_provider_keys(link)

    def test_duplicate_entry_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"providers.env"
            p.write_text("OPENAI_API_KEY=a\nOPENAI_API_KEY=b\nANTHROPIC_API_KEY=c\n")
            p.chmod(0o600)
            with self.assertRaises(ValueError):
                load_provider_keys(p)
