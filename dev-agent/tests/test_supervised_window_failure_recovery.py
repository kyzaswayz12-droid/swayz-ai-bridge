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
            "snapshot":"/var/lib/swayz-executor/snapshots/job1",
            "snapshot_root":"/var/lib/swayz-executor/snapshots",
            "expected_hashes":{"x":"c"*64}, "image_digest":"sha256:"+"d"*64
        }
        self.config = {
            "job_db":window.JOBS, "budget_db":"/var/lib/swayz-executor/budget.sqlite3",
            "signing_key_file":window.KEY,
            "approved_image_digests":["sha256:"+"d"*64]
        }

    def run_window(self, failure=None):
        def protected(path, *, max_bytes=32768):
            if path == window.CONFIG:
                self.assertEqual(max_bytes, 32768)
                return self.config
            self.assertEqual(max_bytes, 131072)
            return self.metadata
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
            window, "admit_supervised_smoke"), patch.object(
            window, "verify_snapshot_before_execution"), patch.object(
            window.Path, "stat", autospec=True) as stat:
            real_stat = Path.stat
            # Only the deployed script ownership check needs a root fixture.
            stat.side_effect = lambda self, *a, **k: type(
                "S", (), {"st_uid":0, "st_mode":0o100600})()
            return window.run("job1", "/protected/job1.json")

    def test_resume_rejects_promote_combination(self):
        with self.assertRaises(PermissionError):
            window.run("job1", "/protected/job1.json", held_job=True, resume_admitted=True)

    def test_resume_requires_existing_admission(self):
        with patch.object(window.os, "geteuid", return_value=0), patch.object(
            window.sys.stdin, "isatty", return_value=True), patch.object(
            window, "protected_json", side_effect=lambda p, **kw: self.config if p == window.CONFIG else self.metadata), patch.object(
            window, "verify_snapshot_before_execution"), patch(
            "builtins.input", return_value="AUTHORISE job1"), patch.object(
            window, "EmergencyStop", side_effect=lambda _: Stop()), patch.object(
            window, "cmd"), patch.object(
            window, "require_existing_admission", side_effect=PermissionError("Already used")), patch.object(
            window.Path, "stat", autospec=True) as stat:
            stat.side_effect = lambda self, *a, **k: type("S", (), {"st_uid":0,"st_mode":0o100600})()
            with self.assertRaisesRegex(PermissionError, "Already used"):
                window.run("job1", "/protected/job1.json", resume_admitted=True)
        self.assertTrue(Stop.stopped)

    def test_prepared_dispatch_never_resigns_or_readmits(self):
        with patch.object(window.os, "geteuid", return_value=0), patch.object(
            window.sys.stdin, "isatty", return_value=True), patch(
            "builtins.input", return_value="AUTHORISE job1"), patch.object(
            window, "protected_json", side_effect=lambda p, **kw: self.config if p == window.CONFIG else self.metadata), patch.object(
            window, "EmergencyStop", side_effect=lambda _: Stop()), patch.object(
            window, "cmd"), patch.object(
            window, "verify_snapshot_before_execution"), patch.object(
            window, "validate_prepared_request"), patch.object(
            window, "require_existing_admission"), patch.object(
            window, "run_one_supervised_handoff") as signing, patch.object(
            window, "admit_held_task") as admission, patch.object(
            window, "dispatch_prepared_offline_job", return_value={"state":"passed", "cleanup_verified":True}) as dispatch, patch.object(
            window.Path, "stat", autospec=True) as stat:
            stat.side_effect = lambda self, *a, **k: type("S", (), {"st_uid":0,"st_mode":0o100600})()
            self.assertEqual(window.run("job1", "/protected/job1.json", dispatch_prepared=True)["state"], "passed")
            signing.assert_not_called()
            admission.assert_not_called()
            dispatch.assert_called_once()
        self.assertTrue(Stop.stopped)

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


class ExistingAdmissionDateTests(unittest.TestCase):
    """A cross-midnight resume must retain all three authoritative records."""

    def check(self, queue_day="2026-11-20", admitted_day="2026-11-20",
              queue_state="claimed", journal_state="admitted", request_exists=False):
        from datetime import datetime, timezone
        from unittest.mock import patch
        rows = {
            window.QUEUE: [(queue_day, queue_state)],
            window.JOBS: [(admitted_day,)],
            window.JOURNAL: [(journal_state,)],
        }
        class FakeConnection:
            def __init__(self, path):
                self.path = path
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, query, params):
                if params != ("swayzoffline20261120a",):
                    raise AssertionError("Unexpected job identity")
                return self
            def fetchall(self):
                return rows[self.path]
        def connect(uri, uri_flag=False, **kwargs):
            path = uri.removeprefix("file:").split("?")[0]
            return FakeConnection(path)
        real_exists = Path.exists
        with patch.object(window, "PersistentStopGuard", create=True), patch(
            "agent.persistent_stop_guard.PersistentStopGuard"
        ) as guard, patch.object(window.sqlite3, "connect", side_effect=connect), patch.object(
            window.Path, "is_file", return_value=True
        ), patch.object(window.Path, "is_symlink", return_value=False), patch.object(
            window.Path, "exists", return_value=request_exists
        ), patch.object(window, "datetime") as dt:
            dt.strptime.side_effect = datetime.strptime
            dt.now.return_value = datetime(2026, 11, 21, tzinfo=timezone.utc)
            window.require_existing_admission("swayzoffline20261120a")
            guard.return_value.require_running.assert_called_once()

    def test_cross_midnight_original_admission_is_accepted(self):
        self.check()

    def test_mismatched_original_dates_rejected(self):
        with self.assertRaises(PermissionError):
            self.check(admitted_day="2026-11-21")

    def test_unclaimed_job_rejected(self):
        with self.assertRaises(PermissionError):
            self.check(queue_state="pending")

    def test_consumed_journal_rejected(self):
        with self.assertRaises(PermissionError):
            self.check(journal_state="passed")

    def test_future_dated_admission_rejected(self):
        with self.assertRaises(PermissionError):
            self.check(queue_day="2026-11-22", admitted_day="2026-11-22")

    def test_existing_signed_request_requires_reconciliation(self):
        with self.assertRaises(PermissionError):
            self.check(request_exists=True)
