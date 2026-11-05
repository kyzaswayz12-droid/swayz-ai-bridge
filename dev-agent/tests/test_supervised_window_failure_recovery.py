"""Offline fault-injection tests for the real supervised window entrypoint.

No root privileges, systemd calls, Docker or database changes.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

SCRIPT = Path(__file__).resolve().parents[1] / "deployment" / "swayz_one_shot_window.py"
spec = importlib.util.spec_from_file_location("swayz_one_shot_window", SCRIPT)
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)


class Stop:
    stopped = True
    def is_stopped(self):
        return self.stopped
    def enable(self, *, owner_authorised=False):
        if owner_authorised is not True:
            raise PermissionError("No approval")
        self.stopped = False
    def stop(self):
        self.stopped = True
    def close(self):
        pass


class SupervisedWindowFailureTests(unittest.TestCase):
    def setUp(self):
        Stop.stopped = True
        self.events = []
        self.metadata = {
            "job_id":"job1", "commit_sha":"a"*40, "manifest_sha256":"b"*64,
            "snapshot":"/snap/job1", "snapshot_root":"/snap",
            "expected_hashes":{"x":"c"*64}, "image_digest":"sha256:"+"d"*64
        }
        self.config = {
            "job_db":window.JOBS, "budget_db":"/var/lib/swayz-executor/budget.sqlite3",
            "signing_key_file":window.KEY,
            "approved_image_digests":["sha256:"+"d"*64]
        }

    def run_window(self, failure=None):
        def protected(path):
            return self.config if path == window.CONFIG else self.metadata
        def cmd(*args, **kwargs):
            self.events.append(args[0] + ":" + args[1])
            if failure == "watchdog" and args[0] == "systemd-run":
                raise RuntimeError("watchdog failure")
        def handoff(**kwargs):
            self.events.append("handoff")
            if failure == "handoff":
                raise RuntimeError("execution failed")
            return {"state":"passed", "cleanup_verified":True}
        with patch.object(window.os, "geteuid", return_value=0), patch.object(
            window.sys.stdin, "isatty", return_value=True), patch(
            "builtins.input", return_value="AUTHORISE job1"), patch.object(
            window, "protected_json", side_effect=protected), patch.object(
            window, "EmergencyStop", side_effect=lambda _: Stop()), patch.object(
            window, "cmd", side_effect=cmd), patch.object(
            window, "run_one_supervised_handoff", side_effect=handoff), patch.object(
            window.Path, "stat", autospec=True) as stat:
            real_stat = Path.stat
            # Only the deployed script ownership check needs a root fixture.
            stat.side_effect = lambda self, *a, **k: type(
                "S", (), {"st_uid":0, "st_mode":0o100600})()
            return window.run("job1", "/protected/job1.json")

    def test_success_restores_stop(self):
        self.assertEqual(self.run_window()["state"], "passed")
        self.assertTrue(Stop.stopped)
        self.assertIn("handoff", self.events)

    def test_handoff_exception_restores_stop(self):
        with self.assertRaises(RuntimeError):
            self.run_window("handoff")
        self.assertTrue(Stop.stopped)
        self.assertIn("systemctl:start", self.events)

    def test_watchdog_failure_never_releases_stop(self):
        with self.assertRaises(RuntimeError):
            self.run_window("watchdog")
        self.assertTrue(Stop.stopped)
        self.assertNotIn("handoff", self.events)
