"""Quarantined, queue-only task staging; never part of the executable task queue.

Operator provisions this separate database in advance. A held record is not an
admitted job and cannot be claimed by DevelopmentTaskQueue. No stop release.
"""
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def provision_held_tasks(path):
    """Operator-only setup. Do not call from an inbound Slack request."""
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS held_tasks (
            job_id TEXT PRIMARY KEY,
            day_utc TEXT NOT NULL,
            task TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state='held')
        )""")


def stage_held_task(*, held_db, executable_db, job_id, task, now):
    """Store one authenticated request without admitting or executing it.

    Caller must independently verify Slack identity and signed control message.
    This does not override the global stop and does not spend a job quota slot.
    """
    if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
        raise ValueError("Invalid job ID")
    if not isinstance(task, str) or not 1 <= len(task.strip()) <= 400:
        raise ValueError("Invalid task")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    held = Path(held_db)
    executable = Path(executable_db)
    for path in (held, executable):
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise PermissionError("Pre-provisioned database required")
    if held.resolve() == executable.resolve():
        raise PermissionError("Held tasks must be physically separate from executable queue")
    with sqlite3.connect(f"file:{executable}?mode=ro", uri=True) as db:
        columns = {r[1] for r in db.execute("PRAGMA table_info(development_tasks)")}
        if not {"job_id", "state"}.issubset(columns):
            raise PermissionError("Executable queue schema invalid")
        if db.execute("SELECT 1 FROM development_tasks WHERE job_id=?", (job_id,)).fetchone():
            raise PermissionError("Job already exists in executable queue")
    with sqlite3.connect(str(held), isolation_level=None, timeout=10) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            columns = {r[1] for r in db.execute("PRAGMA table_info(held_tasks)")}
            if columns != {"job_id", "day_utc", "task", "state"}:
                raise PermissionError("Held queue schema invalid")
            db.execute(
                "INSERT INTO held_tasks(job_id,day_utc,task,state) VALUES(?,?,?,?)",
                (job_id, now.astimezone(timezone.utc).date().isoformat(), task.strip(), "held"))
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return {"job_id": job_id, "state": "held"}
