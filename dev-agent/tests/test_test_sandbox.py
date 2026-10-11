import tempfile
import unittest
from pathlib import Path
from agent.test_sandbox import build_test_invocation

IMAGE="python:3.12.7-slim-bookworm@sha256:"+"a"*64

class SandboxTests(unittest.TestCase):
    def test_restricted_command(self):
        with tempfile.TemporaryDirectory() as d:
            result=build_test_invocation(str(Path(d).resolve()),image=IMAGE)
            self.assertIn("--network=none",result.argv)
            self.assertIn("--read-only",result.argv)
            self.assertIn("--cap-drop=ALL",result.argv)
            self.assertIn("--security-opt=no-new-privileges",result.argv)
            self.assertIn("--user",result.argv)
            self.assertIn("65534:65534",result.argv)
            self.assertNotIn("--privileged",result.argv)

    def test_reject_unpinned_image(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                build_test_invocation(str(Path(d).resolve()),image="python:latest")

    def test_reject_placeholder_digest(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                build_test_invocation(str(Path(d).resolve()),
                    image="python:3.12.7-slim-bookworm@sha256:"+"0"*64)

    def test_reject_resource_overrides(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                build_test_invocation(str(Path(d).resolve()),image=IMAGE,memory_mb=4096)
            with self.assertRaises(ValueError):
                build_test_invocation(str(Path(d).resolve()),image=IMAGE,cpus="4")
