"""Offline-only atomic claim of a previously admitted development task.

No scheduler, model calls, signing, Docker, or GitHub writes.
A claim is NOT permission to execute. The privileged worker must independently
verify provenance, stop, journal and budget at the execution boundary.
"""
import re
import sqlite3
from pathlib import Path
from .persistent_stop_guard import PersistentStopGuard

_JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def claim_admitted_task(*, queue_db, job_db, control_db, job_id):
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        raise ValueError("Invalid job ID")
    guard = PersistentStopGuard(control_db)
    guard.require_running()
    q, j = Path(queue_db), Path(job_db)
    if any(not p.is_absolute() or p.is_symlink() or not p.is_file() for p in (q, j)):
        raise PermissionError("Required database missing")
    with sqlite3.connect(j.as_uri() + "?mode=ro", uri=True, timeout=10) as jobs:
        with sqlite3.connect(str(q), timeout=10, isolation_level=None) as queue:
            queue.execute("BEGIN IMMEDIATE")
            try:
                row = queue.execute(
                    "SELECT day_utc,task FROM development_tasks "
                    "WHERE job_id=? AND state='queued'", (job_id,)
                ).fetchone()
                if row is None:
                    queue.execute("ROLLBACK")
                    return False
                admitted = jobs.execute(
                    "SELECT day_utc FROM admitted_jobs WHERE job_id=?", (job_id,)
                ).fetchall()
                if admitted != [(row[0],)]:
                    raise PermissionError("Admission mismatch")
                guard.require_running()
                result = queue.execute(
                    "UPDATE development_tasks SET state='claimed' "
                    "WHERE job_id=? AND state='queued'", (job_id,)
                )
                if result.rowcount != 1:
                    raise PermissionError("Claim lost")
                guard.require_running()
                queue.execute("COMMIT")
                return True
            except BaseException:
                if queue.in_transaction:
                    queue.execute("ROLLBACK")
                raise
