"""Regression coverage for separate protected config and signed-request size caps."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import trusted_executor_entrypoint as entry


class ProtectedRequestSizeTests(unittest.TestCase):
    def test_request_accepts_full_hash_manifest_but_config_stays_small(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "request.json"
            p.write_text(json.dumps({"expected_hashes": {str(i): "a" * 64 for i in range(600)}}))
            self.assertGreater(p.stat().st_size, 32768)
            self.assertLess(p.stat().st_size, 131072)
            with patch.object(entry.Path, "stat", autospec=True) as mocked:
                real_stat = Path.stat
                def stat(path, *args, **kwargs):
                    result = real_stat(path, *args, **kwargs)
                    return type("ProtectedStat", (), {"st_uid": 0, "st_mode": 0o100600, "st_size": result.st_size})()
                mocked.side_effect = stat
                with self.assertRaisesRegex(PermissionError, "too large"):
                    entry._protected_json(p)
                self.assertEqual(len(entry._protected_json(p, max_bytes=131072)["expected_hashes"]), 600)

    def test_oversized_request_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "request.json"
            p.write_text(json.dumps({"hashes": "a" * 131073}))
            with patch.object(entry.Path, "stat", autospec=True) as mocked:
                real_stat = Path.stat
                mocked.side_effect = lambda path, *a, **kw: type("ProtectedStat", (), {"st_uid": 0, "st_mode": 0o100600, "st_size": real_stat(path, *a, **kw).st_size})()
                with self.assertRaisesRegex(PermissionError, "too large"):
                    entry._protected_json(p, max_bytes=131072)


if __name__ == "__main__":
    unittest.main()
