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
