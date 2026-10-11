"""Persistent job admission with replay protection.

The trusted worker must still fetch and verify an immutable commit before
executing tests. This module never runs Docker or Git commands.
"""
import sqlite3
import time
from .test_jobs import verify_job

class JobInbox:
    def __init__(self,path=":memory:"):
        self.db=sqlite3.connect(path,timeout=10,isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS accepted_jobs(
            job_id TEXT PRIMARY KEY, commit_sha TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('accepted','blocked','complete')),
            accepted_at INTEGER NOT NULL)""")

    def accept(self,raw: bytes,signature: str,secret: bytes) -> bool:
        job=verify_job(raw,signature,secret)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            result=self.db.execute("INSERT OR IGNORE INTO accepted_jobs VALUES(?,?,?,?)",
                                   (job.job_id,job.commit_sha,"accepted",int(time.time())))
            self.db.execute("COMMIT")
            return result.rowcount==1
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def status(self,job_id: str):
        row=self.db.execute("SELECT status FROM accepted_jobs WHERE job_id=?",(job_id,)).fetchone()
        return row[0] if row else None

    def close(self):
        self.db.close()
