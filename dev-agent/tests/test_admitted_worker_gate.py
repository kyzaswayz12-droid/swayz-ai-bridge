"""Offline admission/stop tests; no Docker or network access."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent.trusted_docker_executor import validate_admitted_worker_plan

DIGEST = "sha256:" + "a" * 64


class AdmittedWorkerGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stop = self.root / "stop.db"
        self.journal = self.root / "journal.db"
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY, stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES (1,1)")
        with sqlite3.connect(self.journal) as db:
            db.execute("CREATE TABLE worker_jobs(job_id TEXT PRIMARY KEY, state TEXT)")
            db.execute("INSERT INTO worker_jobs VALUES ('job1','admitted')")
        self.snaproot = self.root / "snapshots"
        self.snaproot.mkdir()
        self.snapshot = self.snaproot / "job1"
        self.snapshot.mkdir()
        f = self.snapshot / "sample.txt"
        f.write_bytes(b"verified")
        f.chmod(0o444)
        self.snapshot.chmod(0o555)
        self.hashes = {"sample.txt": hashlib.sha256(b"verified").hexdigest()}

    def tearDown(self):
        self.snapshot.chmod(0o755)
        (self.snapshot / "sample.txt").chmod(0o644)

    def check(self, **kwargs):
        args = dict(control_db=str(self.stop), journal_db=str(self.journal),
                    job_id="job1", snapshot=str(self.snapshot),
                    snapshot_root=str(self.snaproot), expected_hashes=self.hashes,
                    image_digest=DIGEST, approved_image_digests=frozenset({DIGEST}))
        args.update(kwargs)
        return validate_admitted_worker_plan(**args)

    def test_stopped_rejected(self):
        with self.assertRaises(PermissionError):
            self.check()

    def test_admitted_and_unstopped_passes_validation_only(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=0 WHERE id=1")
        plan = self.check()
        self.assertFalse(plan.lifecycle.executes)

    def test_unadmitted_rejected(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=0 WHERE id=1")
        with sqlite3.connect(self.journal) as db:
            db.execute("UPDATE worker_jobs SET state='running' WHERE job_id='job1'")
        with self.assertRaises(PermissionError):
            self.check()

    def test_missing_control_db_rejected_without_creation(self):
        missing = self.root / "missing.db"
        with self.assertRaises(PermissionError):
            self.check(control_db=str(missing))
        self.assertFalse(missing.exists())

    def test_missing_journal_db_rejected_without_creation(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=0 WHERE id=1")
        missing = self.root / "missing-journal.db"
        with self.assertRaises(PermissionError):
            self.check(journal_db=str(missing))
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
