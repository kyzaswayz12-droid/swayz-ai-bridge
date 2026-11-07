"""Read-only, fail-closed queue discovery.

This component does not claim jobs, sign requests, call providers, or execute
Docker. A separately authenticated worker must recheck admission and stop
at the atomic claim and privileged execution boundaries.
"""
import re
import sqlite3
from pathlib import Path
from .persistent_stop_guard import PersistentStopGuard

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def next_queued_job(*, queue_db, job_db, control_db):
    guard = PersistentStopGuard(control_db)
    guard.require_running()
    paths = [Path(queue_db), Path(job_db)]
    if any(not p.is_absolute() or p.is_symlink() or not p.is_file() for p in paths):
        raise PermissionError("Required database missing")
    try:
        with sqlite3.connect(paths[0].as_uri() + "?mode=ro", uri=True, timeout=5) as queue:
            with sqlite3.connect(paths[1].as_uri() + "?mode=ro", uri=True, timeout=5) as jobs:
                qcols = {r[1] for r in queue.execute("PRAGMA table_info(development_tasks)")}
                jcols = {r[1] for r in jobs.execute("PRAGMA table_info(admitted_jobs)")}
                if not {"job_id", "day_utc", "task", "state"} <= qcols:
                    raise PermissionError("Queue schema incompatible")
                if not {"job_id", "day_utc"} <= jcols:
                    raise PermissionError("Admission schema incompatible")
                row = queue.execute(
                    "SELECT job_id,day_utc,task FROM development_tasks "
                    "WHERE state='queued' ORDER BY day_utc,job_id LIMIT 1"
                ).fetchone()
                if row is None:
                    guard.require_running()
                    return None
                job_id, day, task = row
                if (not isinstance(job_id, str) or not _ID.fullmatch(job_id)
                        or not isinstance(day, str) or not isinstance(task, str)
                        or not 1 <= len(task.strip()) <= 400):
                    raise PermissionError("Invalid queued task")
                admission = jobs.execute(
                    "SELECT day_utc FROM admitted_jobs WHERE job_id=?", (job_id,)
                ).fetchall()
                if admission != [(day,)]:
                    raise PermissionError("Queued job admission mismatch")
                guard.require_running()
                return {"job_id": job_id, "task": task}
    except sqlite3.Error as exc:
        raise PermissionError("Queue or admission ledger unreadable") from exc
