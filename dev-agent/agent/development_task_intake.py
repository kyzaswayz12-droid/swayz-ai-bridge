"""Durable, fail-closed intake of authenticated development tasks.

Called only after Slack signature, user/channel allowlist, and deduplication
are verified by the Bridge. No AI calls, Docker execution or GitHub writes.
"""
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def submit_verified_task(*, db_path, job_db, control_db, job_id, task, now):
    if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
        raise ValueError("Invalid job ID")
    if not isinstance(task, str) or not 1 <= len(task.strip()) <= 400:
        raise ValueError("Invalid development task")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    from .persistent_stop_guard import PersistentStopGuard
    guard = PersistentStopGuard(control_db)
    guard.require_running()
    path = Path(db_path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise PermissionError("Pre-provisioned task queue required")
    day = now.astimezone(timezone.utc).date().isoformat()
    # Reject a malformed or duplicate queue before consuming a quota slot.
    # The canonical admission ledger remains the final duplicate authority.
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10) as queue:
        columns = {row[1] for row in queue.execute("PRAGMA table_info(development_tasks)")}
        if not {"job_id", "day_utc", "task", "state"}.issubset(columns):
            raise PermissionError("Development queue schema incompatible")
        if queue.execute("SELECT 1 FROM development_tasks WHERE job_id=?", (job_id,)).fetchone():
            raise PermissionError("Duplicate development task")
    # Use the existing authoritative 20-job quota, never a second quota.
    # A failed queue insert conservatively retains the admission slot.
    from .daily_job_quota import DailyJobQuota
    quota = DailyJobQuota(job_db)
    try:
        if not quota.admit(job_id, now, daily_limit=20):
            raise PermissionError("Job already admitted")
    finally:
        quota.close()
    with sqlite3.connect(str(path), timeout=10, isolation_level=None) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            guard.require_running()
            if db.execute("SELECT 1 FROM development_tasks WHERE job_id=?", (job_id,)).fetchone():
                raise PermissionError("Duplicate job")
            db.execute(
                "INSERT INTO development_tasks(job_id,day_utc,task,state) VALUES(?,?,?,?)",
                (job_id, day, task.strip(), "queued"))
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return job_id


def provision_task_queue(path):
    """Operator-only provisioning; never invoked by a Slack request."""
    db = sqlite3.connect(path)
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS development_tasks(
            job_id TEXT PRIMARY KEY,
            day_utc TEXT NOT NULL,
            task TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('queued','claimed','blocked','done'))
        )""")
        db.commit()
    finally:
        db.close()


class DevelopmentTaskQueue:
    """Existing durable queue interface; never executes a task itself."""
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_absolute() or self.path.is_symlink() or not self.path.is_file():
            raise PermissionError("Task queue missing")

    def get(self, job_id):
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT task,state FROM development_tasks WHERE job_id=?", (job_id,)
            ).fetchone()
        return {"task": row[0], "state": row[1]} if row else None

    def claim(self, job_id):
        with sqlite3.connect(self.path, timeout=10) as db:
            result = db.execute(
                "UPDATE development_tasks SET state='claimed' "
                "WHERE job_id=? AND state='queued'", (job_id,))
            return result.rowcount == 1

    def finish(self, job_id, state):
        if state not in ("blocked", "done"):
            raise ValueError("Invalid terminal task state")
        with sqlite3.connect(self.path, timeout=10) as db:
            result = db.execute(
                "UPDATE development_tasks SET state=? "
                "WHERE job_id=? AND state='claimed'", (state, job_id))
            if result.rowcount != 1:
                raise PermissionError("Task state transition rejected")
