"""Durable fail-closed worker execution journal.

Does not execute jobs. Unknown/incomplete work remains blocked after restart.
"""
import sqlite3
from datetime import datetime, timezone


class WorkerJournal:
    def __init__(self, path):
        if not isinstance(path, str) or not path or path == ":memory:":
            raise ValueError("Persistent journal path required")
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS worker_jobs(
            job_id TEXT PRIMARY KEY,
            state TEXT NOT NULL CHECK(state IN ('admitted','running','passed','failed','blocked')),
            updated_utc TEXT NOT NULL,
            exit_code INTEGER,
            result_excerpt TEXT NOT NULL DEFAULT ''
        )""")

    def record_admission(self, job_id):
        if not isinstance(job_id, str) or not 1 <= len(job_id) <= 64:
            raise ValueError("Invalid job ID")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            result = self.db.execute(
                "INSERT OR IGNORE INTO worker_jobs(job_id,state,updated_utc) VALUES (?,?,?)",
                (job_id, "admitted", datetime.now(timezone.utc).isoformat()))
            self.db.execute("COMMIT")
            return result.rowcount == 1
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def transition(self, job_id, expected, state, *, exit_code=None, excerpt=""):
        allowed = {("admitted", "running"), ("running", "passed"),
                   ("running", "failed"), ("running", "blocked"),
                   ("admitted", "blocked")}
        if (expected, state) not in allowed:
            raise ValueError("Invalid worker transition")
        if not isinstance(excerpt, str):
            raise ValueError("Invalid result")
        if len(excerpt) > 12000:
            excerpt = excerpt[:12000]
        self.db.execute("BEGIN IMMEDIATE")
        try:
            result = self.db.execute(
                """UPDATE worker_jobs SET state=?,updated_utc=?,exit_code=?,
                   result_excerpt=? WHERE job_id=? AND state=?""",
                (state, datetime.now(timezone.utc).isoformat(),
                 exit_code, excerpt, job_id, expected))
            if result.rowcount != 1:
                raise PermissionError("Unexpected job state")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def recover_incomplete(self):
        """Block incomplete jobs; a separate worker must clean orphan containers."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            result = self.db.execute(
                """UPDATE worker_jobs SET state='blocked',updated_utc=?
                   WHERE state IN ('admitted','running')""",
                (datetime.now(timezone.utc).isoformat(),))
            self.db.execute("COMMIT")
            return result.rowcount
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def status(self, job_id):
        return self.db.execute(
            "SELECT state,exit_code,result_excerpt FROM worker_jobs WHERE job_id=?",
            (job_id,)).fetchone()

    def close(self):
        self.db.close()
