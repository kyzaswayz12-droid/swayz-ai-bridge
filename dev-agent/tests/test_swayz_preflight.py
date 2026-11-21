"""Fail-closed preflight tests against disposable SQLite ledgers, no execution."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from deployment import swayz_preflight as preflight

JOB = "swayzoffline20261120a"
DAY = "2026-11-20"


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.paths = {name: str(root / (name + ".db")) for name in ("jobs", "queue", "journal", "stop")}
        self.paths.update(metadata=str(root / "metadata.json"), config=str(root / "config.json"),
                          key=str(root / "signing.key"), inbox=str(root / "requests"))
        self.metadata = {"job_id": JOB, "snapshot": str(root / "snapshots" / JOB),
                         "snapshot_root": str(root / "snapshots"), "expected_hashes": {"file": "sha"}}
        self.config = {"job_db": self.paths["jobs"], "signing_key_file": self.paths["key"]}
        with sqlite3.connect(self.paths["jobs"]) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT, day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES(?,?)", (JOB, DAY))
        with sqlite3.connect(self.paths["queue"]) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT,day_utc TEXT,state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES(?,?,?)", (JOB, DAY, "claimed"))
        with sqlite3.connect(self.paths["journal"]) as db:
            db.execute("CREATE TABLE worker_jobs(job_id TEXT,state TEXT)")
            db.execute("INSERT INTO worker_jobs VALUES(?,?)", (JOB, "admitted"))
        with sqlite3.connect(self.paths["stop"]) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,1)")

    def inspect(self):
        def protected(path, **_):
            if path == self.paths["metadata"]:
                return self.metadata
            if path == self.paths["config"]:
                return self.config
            raise AssertionError("unexpected protected input")
        with (patch.object(preflight.window, "protected_json", side_effect=protected),
              patch.object(preflight.window, "validate_prepared_request") as signed,
              patch.object(preflight, "verify_snapshot_before_execution") as snapshot):
            result = preflight.inspect(JOB, paths=self.paths)
            # No dispatcher, stop enable, admission or journal-transition hooks are invoked.
            if result["checks"].get("signed_request") == "PASS":
                signed.assert_called_once()
            if result["checks"].get("snapshot_integrity") == "PASS":
                snapshot.assert_called_once()
            return result

    def test_valid_claimed_job_reports_review_not_execution(self):
        result = self.inspect()
        self.assertEqual(result["state"], "READY_FOR_SUPERVISED_REVIEW")
        self.assertFalse(result["execution_authorised"])
        self.assertEqual(result["original_admission"], DAY)
        self.assertTrue(all(value == "PASS" for value in result["checks"].values()))

    def test_disengaged_stop_blocks(self):
        with sqlite3.connect(self.paths["stop"]) as db:
            db.execute("UPDATE agent_control SET stopped=0")
        result = self.inspect()
        self.assertEqual(result["checks"]["emergency_stop_engaged"], "FAIL")
        self.assertEqual(result["state"], "BLOCKED")

    def test_unclaimed_job_blocks(self):
        with sqlite3.connect(self.paths["queue"]) as db:
            db.execute("UPDATE development_tasks SET state='pending'")
        result = self.inspect()
        self.assertEqual(result["checks"]["queue_claim"], "FAIL")

    def test_journal_replay_blocks(self):
        with sqlite3.connect(self.paths["journal"]) as db:
            db.execute("UPDATE worker_jobs SET state='running'")
        result = self.inspect()
        self.assertEqual(result["checks"]["journal"], "FAIL")

    def test_missing_job_blocks(self):
        with sqlite3.connect(self.paths["jobs"]) as db:
            db.execute("DELETE FROM admitted_jobs")
        result = self.inspect()
        self.assertEqual(result["checks"]["original_admission"], "FAIL")
        self.assertEqual(result["checks"]["daily_quota"], "BLOCKED")

    def test_quota_over_limit_blocks(self):
        with sqlite3.connect(self.paths["jobs"]) as db:
            db.executemany("INSERT INTO admitted_jobs VALUES(?,?)",
                           [(f"other{i}", DAY) for i in range(20)])
        result = self.inspect()
        self.assertEqual(result["checks"]["daily_quota"], "FAIL")

    def test_sqlite_ledgers_unchanged(self):
        before = {k: Path(self.paths[k]).read_bytes()
                  for k in ("jobs", "queue", "journal", "stop")}
        self.inspect()
        after = {k: Path(self.paths[k]).read_bytes()
                 for k in ("jobs", "queue", "journal", "stop")}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
