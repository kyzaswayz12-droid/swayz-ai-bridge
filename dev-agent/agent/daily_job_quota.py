"""Durable UTC daily development-job admission quota.

This controls job counts only; API spending is governed independently.
Do not use this as an authorisation to execute jobs.
"""
from datetime import datetime, timezone
import sqlite3


class DailyJobQuota:
    def __init__(self, path):
        if not path or path == ":memory:":
            raise ValueError("Persistent database path required")
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS admitted_jobs (
            job_id TEXT PRIMARY KEY,
            day_utc TEXT NOT NULL
        )""")

    def admit(self, job_id, now, *, daily_limit=20):
        if not isinstance(job_id, str) or not (1 <= len(job_id) <= 128):
            raise ValueError("Invalid job ID")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Timezone-aware clock required")
        if type(daily_limit) is not int or daily_limit < 1:
            raise ValueError("Invalid daily limit")
        day = now.astimezone(timezone.utc).date().isoformat()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT 1 FROM admitted_jobs WHERE job_id=?", (job_id,)).fetchone():
                self.db.execute("COMMIT")
                return False
            count = self.db.execute(
                "SELECT COUNT(*) FROM admitted_jobs WHERE day_utc=?", (day,)
            ).fetchone()[0]
            if count >= daily_limit:
                raise ValueError("Daily development job quota exhausted")
            self.db.execute(
                "INSERT INTO admitted_jobs(job_id,day_utc) VALUES (?,?)", (job_id,day)
            )
            self.db.execute("COMMIT")
            return True
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def close(self):
        self.db.close()
