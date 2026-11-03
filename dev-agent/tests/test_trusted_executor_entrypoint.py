"""Operator entrypoint safety tests; never executes Docker."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent.trusted_executor_entrypoint import _protected_json, main


class OperatorEntrypointTests(unittest.TestCase):
    def test_request_outside_protected_inbox_rejected(self):
        with patch("agent.trusted_executor_entrypoint.os.geteuid", return_value=0), \\
             patch("agent.trusted_executor_entrypoint._protected_json", return_value={}):
            with self.assertRaises(PermissionError):
                main(["--supervised-once", "--request", "/tmp/job1.json"])

    def test_request_filename_must_match_job(self):
        with patch("agent.trusted_executor_entrypoint.os.geteuid", return_value=0), \\
             patch("agent.trusted_executor_entrypoint._protected_json", side_effect=[{}, {"job_id": "other"}]):
            with self.assertRaises(PermissionError):
                main(["--supervised-once", "--request", "/var/lib/swayz-executor/requests/job1.json"])

    def test_non_root_refused_before_reading_request(self):
        with patch("agent.trusted_executor_entrypoint.os.geteuid", return_value=1000):
            with self.assertRaises(PermissionError):
                main(["--supervised-once", "--request", "/nonexistent"])

    def test_explicit_supervision_required(self):
        with patch("agent.trusted_executor_entrypoint.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                main(["--request", "/nonexistent"])

    def test_world_readable_request_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "request.json"
            p.write_text("{}")
            p.chmod(0o644)
            with self.assertRaises(PermissionError):
                _protected_json(str(p))

    def test_symlink_request_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "request.json"
            p.write_text("{}")
            link = Path(d) / "link.json"
            link.symlink_to(p)
            with self.assertRaises(PermissionError):
                _protected_json(str(link))
