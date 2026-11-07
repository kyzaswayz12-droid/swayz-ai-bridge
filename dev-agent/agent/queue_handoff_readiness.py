"""Offline-only signed handoff readiness inspection.

This module never reads signing keys, signs payloads, claims jobs, invokes
systemd, or authorises Docker execution. The privileged operator must
independently verify the actual request and admission at execution time.
"""
import re
import sqlite3
from pathlib import Path
from .persistent_stop_guard import PersistentStopGuard

_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def inspect_handoff_readiness(*, job_id, queue_db, job_db, control_db):
    if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise ValueError("Invalid job ID")
    guard = PersistentStopGuard(control_db)
    guard.require_running()
    paths = (Path(queue_db), Path(job_db))
    if any(not p.is_absolute() or p.is_symlink() or not p.is_file() for p in paths):
        raise PermissionError("Required state missing")
    with sqlite3.connect(paths[0].as_uri() + "?mode=ro", uri=True) as queue:
        record = queue.execute(
            "SELECT day_utc,state FROM development_tasks WHERE job_id=?", (job_id,)
        ).fetchall()
    if len(record) != 1 or record[0][1] != "claimed":
        raise PermissionError("Task must be claimed")
    with sqlite3.connect(paths[1].as_uri() + "?mode=ro", uri=True) as jobs:
        admitted = jobs.execute(
            "SELECT day_utc FROM admitted_jobs WHERE job_id=?", (job_id,)
        ).fetchall()
    if admitted != [(record[0][0],)]:
        raise PermissionError("Admission mismatch")
    guard.require_running()
    return {"job_id": job_id, "state": "requires_operator_signed_handoff"}
