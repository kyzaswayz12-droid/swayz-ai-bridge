"""Single-use root operator execution from an existing protected admission.

Requires an already claimed, admitted job, verified immutable snapshot and
protected metadata. The operator invokes a root-owned systemd template with
ExecStopPost restoration; this entrypoint never accepts a model callback,
retries, prepares admissions, or enables unattended execution.
"""
import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .protected_admission_loader import load_protected_job
from .protected_admission_writer import require_engaged_stop
from .snapshot_reverification import verify_snapshot_before_execution
from .supervised_stop_window import run_supervised_window
from .operator_signed_execution import execute_operator_signed_job

QUEUE = "/var/lib/swayzcontrol/state/development_tasks.db"
JOBS = "/var/lib/swayz-executor/jobs.sqlite3"
JOURNAL = "/var/lib/swayzcontrol/state/journal.db"
STOP = "/var/lib/swayzcontrol/state/stop.db"


def verify_prepared_offline_job(job_id):
    require_engaged_stop()
    job = load_protected_job(job_id)
    if (job["queue_db"] != QUEUE or job["job_db"] != JOBS or
            job["journal_db"] != JOURNAL or job["stop_db"] != STOP or
            job["snapshot_root"] != "/var/lib/swayz-executor/snapshots" or
            job["snapshot"] != job["snapshot_root"] + "/" + job_id or
            job["signing_key_file"] != "/etc/swayz/executor-signing.key" or
            job["request_directory"] != "/var/lib/swayz-executor/requests"):
        raise PermissionError("Unexpected protected runtime metadata")
    day = datetime.now(timezone.utc).date().isoformat()
    for path, statement, expected in (
        (QUEUE, "SELECT day_utc,state FROM development_tasks WHERE job_id=?", [(day, "claimed")]),
        (JOBS, "SELECT day_utc FROM admitted_jobs WHERE job_id=?", [(day,)]),
        (JOURNAL, "SELECT state FROM worker_jobs WHERE job_id=?", [("admitted",)]),
    ):
        p = Path(path)
        if not p.is_file() or p.is_symlink():
            raise PermissionError("Missing protected ledger")
        with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True) as db:
            rows = db.execute(statement, (job_id,)).fetchall()
        if rows != expected:
            raise PermissionError("Job not freshly admitted and unused")
    verify_snapshot_before_execution(job["snapshot"], job["expected_hashes"])
    require_engaged_stop()
    return True


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        raise PermissionError("Authenticated root operator service required")
    # Root invocation is only an OS identity boundary. Deployment must pin
    # the systemd unit and prevent AI-controlled callers from starting it.
    result = run_supervised_window(
        job_id=args.job,
        verify_operator=lambda **kw: os.geteuid() == 0,
        verify_prepared_job=lambda **kw: verify_prepared_offline_job(kw["job_id"]),
        execute_once=lambda **kw: execute_operator_signed_job(job_id=kw["job_id"]),
        stop_db=STOP)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
