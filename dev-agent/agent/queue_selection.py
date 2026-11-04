"""Read-only queue discovery; no execution, claiming, signing or dispatch."""
import sqlite3
from pathlib import Path
from .persistent_stop_guard import PersistentStopGuard

def next_queued_job(*, queue_db, job_db, control_db):
    """Find the oldest queued admitted job; reject missing state."""
    guard = PersistentStopGuard(control_db)
    guard.require_running()
    paths = [Path(queue_db), Path(job_db)]
    if any(not p.is_absolute() or p.is_symlink() or not p.is_file() for p in paths):
        raise PermissionError("Required database missing")
    with sqlite3.connect(paths[0].as_uri() + "?mode=ro", uri=True) as queue:
        with sqlite3.connect(paths[1].as_uri() + "?mode=ro", uri=True) as jobs:
            row = queue.execute(
                "SELECT job_id,day_utc,task FROM development_tasks "
                "WHERE state='queued' ORDER BY day_utc,job_id LIMIT 1"
            ).fetchone()
            if row is None:
                guard.require_running()
                return None
            job_id, day, task = row
            admission = jobs.execute(
                "SELECT day_utc FROM admitted_jobs WHERE job_id=?", (job_id,)
            ).fetchall()
            if admission != [(day,)]:
                raise PermissionError("Queued job admission mismatch")
            guard.require_running()
            return {"job_id": job_id, "task": task}
