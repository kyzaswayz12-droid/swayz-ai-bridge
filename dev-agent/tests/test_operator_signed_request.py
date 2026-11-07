import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from agent.operator_signed_request import prepare_offline_executor_request
from agent.signed_handoff import verify_manifest_job


class OperatorSignedRequestTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.snapshots = root / "snapshots"
        self.snapshots.mkdir()
        self.snapshot = self.snapshots / "job1"
        self.snapshot.mkdir()
        self.inbox = root / "requests"
        self.inbox.mkdir()
        self.key = root / "key"
        self.key.write_bytes(b"T"*32)
        self.queue, self.jobs, self.journal, self.stop = [str(root / n) for n in ("queue.db","jobs.db","journal.db","stop.db")]
        with sqlite3.connect(self.queue) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT,day_utc TEXT,state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES('job1','2026-11-05','claimed')")
        with sqlite3.connect(self.jobs) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT,day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES('job1','2026-11-05')")
        with sqlite3.connect(self.journal) as db:
            db.execute("CREATE TABLE worker_jobs(job_id TEXT,state TEXT)")
            db.execute("INSERT INTO worker_jobs VALUES('job1','admitted')")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")
        self.args = dict(job_id="job1",commit_sha="a"*40,manifest_sha256="b"*64,
            snapshot=str(self.snapshot),snapshot_root=str(self.snapshots),
            expected_hashes={"test.py":"c"*64},image_digest="sha256:"+"d"*64,
            approved_images=frozenset({"sha256:"+"d"*64}),
            queue_db=self.queue,job_db=self.jobs,journal_db=self.journal,
            stop_db=self.stop,signing_key_file=str(self.key),
            request_directory=str(self.inbox),
            now=datetime(2026,11,5,21,tzinfo=timezone.utc))

    def prepare(self, **updates):
        args = dict(self.args)
        args.update(updates)
        original = Path.stat
        with patch("agent.operator_signed_request.os.geteuid",return_value=0), patch(
            "agent.operator_signed_request.verify_snapshot_before_execution"
        ), patch("agent.operator_signed_request.Path.stat", autospec=True) as stat:
            # Tests run as a non-root account; simulate protected ownership
            def protected(path, *a, **kw):
                value = original(path, *a, **kw)
                if path == self.key or path == self.inbox:
                    class Result:
                        st_uid = 0
                        st_mode = 0o100600 if path == self.key else 0o40700
                    return Result()
                return value
            stat.side_effect = protected
            return prepare_offline_executor_request(**args)

    def test_creates_verifiable_signed_request(self):
        path = Path(self.prepare())
        data = json.loads(path.read_text())
        self.assertEqual(data["provider"], "none")
        self.assertIsNone(data["request_id"])
        job = verify_manifest_job(bytes.fromhex(data["raw_hex"]),data["signature"],
                                  b"T"*32,data["expected_manifest"])
        self.assertEqual(job.job_id,"job1")

    def test_duplicate_request_is_not_overwritten(self):
        self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()

    def test_missing_admission_rejected(self):
        with sqlite3.connect(self.jobs) as db:
            db.execute("DELETE FROM admitted_jobs")
        with self.assertRaises(PermissionError):
            self.prepare()

    def test_stop_blocks_request(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=1")
        with self.assertRaises(PermissionError):
            self.prepare()

    def test_unclaimed_task_rejected(self):
        with sqlite3.connect(self.queue) as db:
            db.execute("UPDATE development_tasks SET state='queued'")
        with self.assertRaises(PermissionError):
            self.prepare()
