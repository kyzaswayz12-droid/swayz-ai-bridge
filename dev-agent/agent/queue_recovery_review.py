"""Read-only restart recovery assessment; never automatically retries a claim.

A claimed task may have executed before a crash. It must remain quarantined
until an operator reconciles the authoritative worker journal and artifacts.
"""
import sqlite3
from pathlib import Path
from .persistent_stop_guard import PersistentStopGuard


def inspect_claimed_tasks(*, queue_db, journal_db, control_db):
    guard = PersistentStopGuard(control_db)
    guard.require_running()
    paths = [Path(queue_db), Path(journal_db)]
    if any(not p.is_absolute() or p.is_symlink() or not p.is_file() for p in paths):
        raise PermissionError("Required recovery state missing")
    with sqlite3.connect(paths[0].as_uri() + "?mode=ro", uri=True) as queue:
        with sqlite3.connect(paths[1].as_uri() + "?mode=ro", uri=True) as journal:
            claimed = queue.execute(
                "SELECT job_id FROM development_tasks WHERE state='claimed' ORDER BY job_id"
            ).fetchall()
            results = []
            for (job_id,) in claimed:
                record = journal.execute(
                    "SELECT state FROM worker_jobs WHERE job_id=?", (job_id,)
                ).fetchall()
                if len(record) > 1:
                    raise PermissionError("Ambiguous journal state")
                results.append({
                    "job_id": job_id,
                    "journal_state": record[0][0] if record else "missing",
                    "action": "manual_reconciliation_required",
                })
            guard.require_running()
            return results
