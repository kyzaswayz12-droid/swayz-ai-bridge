"""Operator-only, one-shot promotion of a quarantined Slack task.

This is not a network endpoint. Promotion never releases the emergency stop,
starts a worker, calls a provider or writes to GitHub.
"""
import argparse
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .development_task_intake import submit_verified_task

_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def promote_held_task(*, held_db, executable_db, job_db, stop_db, job_id,
                      now=None, operator_approved=False):
    if os.geteuid() != 0 or operator_approved is not True:
        raise PermissionError("Authenticated root operator approval required")
    if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise ValueError("Invalid job ID")
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware clock required")
    paths = [Path(p) for p in (held_db, executable_db, job_db, stop_db)]
    if any(not p.is_absolute() or p.is_symlink() or not p.is_file() for p in paths):
        raise PermissionError("Pre-provisioned, regular databases required")
    if len({p.resolve() for p in paths}) != len(paths):
        raise PermissionError("Databases must be physically separate")

    # A held task cannot be used to release the stop. Admission requires it
    # to have been opened through the separately authenticated operator process.
    from .persistent_stop_guard import PersistentStopGuard
    PersistentStopGuard(str(paths[3])).require_running()
    with sqlite3.connect(f"file:{paths[0]}?mode=ro", uri=True) as db:
        columns = {r[1] for r in db.execute("PRAGMA table_info(held_tasks)")}
        if columns != {"job_id", "day_utc", "task", "state"}:
            raise PermissionError("Held queue schema invalid")
        record = db.execute(
            "SELECT task,state FROM held_tasks WHERE job_id=?", (job_id,)
        ).fetchone()
    if record is None or record[1] != "held":
        raise PermissionError("Job is not held")
    task = record[0]
    if not isinstance(task, str) or not 1 <= len(task.strip()) <= 400:
        raise ValueError("Invalid held task")

    # Existing admission is authoritative for stop, quota and duplicates.
    # A failure after quota admission deliberately retains its quota slot.
    submit_verified_task(
        db_path=str(paths[1]), job_db=str(paths[2]), control_db=str(paths[3]),
        job_id=job_id, task=task, now=now,
    )
    # Do not delete the original audit record: its job ID can never be
    # admitted twice because the admission ledger and queue reject duplicates.
    return {"job_id": job_id, "state": "queued", "source": "held"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="One-shot operator-approved held task admission")
    parser.add_argument("--job", required=True)
    parser.add_argument("--held-db", default="/var/lib/swayzcontrol/held/tasks.db")
    parser.add_argument("--task-db", default="/var/lib/swayzcontrol/state/development_tasks.db")
    parser.add_argument("--job-db", default="/var/lib/swayz-executor/jobs.sqlite3")
    parser.add_argument("--stop-db", default="/var/lib/swayzcontrol/state/stop.db")
    args = parser.parse_args(argv)
    import json
    result = promote_held_task(
        held_db=args.held_db, executable_db=args.task_db,
        job_db=args.job_db, stop_db=args.stop_db, job_id=args.job,
        operator_approved=True,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
