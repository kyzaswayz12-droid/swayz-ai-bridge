#!/usr/bin/env python3
"""One explicitly authorised supervised Swayz handoff. NOT unattended autonomy.

Run only from a reviewed, root-owned immutable deployment. Never run this
entrypoint from a writable Git checkout. Recovery is independent of the job.
"""
import argparse
import json
import os
import stat
import sqlite3
import subprocess
import sys
from pathlib import Path

# Resolve the paired, immutable deployment's agent package in both the
# interactive process and the independently launched systemd watchdog.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.emergency_stop import EmergencyStop
from agent.one_shot_activation import run_one_supervised_handoff
from agent.restricted_dispatch import dispatch_prepared_offline_job
from agent.signed_handoff import verify_manifest_job
from agent.development_task_intake import submit_verified_task, DevelopmentTaskQueue
from agent.operator_held_promotion import promote_held_task
from agent.worker_journal import WorkerJournal
from agent.snapshot_reverification import verify_snapshot_before_execution
from datetime import datetime, timezone

STOP = "/var/lib/swayzcontrol/state/stop.db"
CONTROL = "swayz-worker-control.service"
INBOX = "/var/lib/swayz-executor/requests"
QUEUE = "/var/lib/swayzcontrol/state/development_tasks.db"
JOBS = "/var/lib/swayz-executor/jobs.sqlite3"
JOURNAL = "/var/lib/swayzcontrol/state/journal.db"
KEY = "/etc/swayz/executor-signing.key"
CONFIG = "/etc/swayz/trusted-executor.json"


def cmd(*args, timeout=20):
    subprocess.run(list(args), check=True, timeout=timeout)


def restore():
    stop = EmergencyStop(STOP)
    try:
        stop.stop()
        if not stop.is_stopped():
            raise RuntimeError("Emergency stop restoration failed")
    finally:
        stop.close()
    cmd("systemctl", "start", CONTROL)


def protected_json(path, *, max_bytes=32768):
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise PermissionError("Protected input missing")
    st = p.stat()
    if st.st_uid != 0 or st.st_mode & 0o077 or not stat.S_ISREG(st.st_mode) or st.st_size > max_bytes:
        raise PermissionError("Unprotected input")
    return json.loads(p.read_text())


def admit_supervised_smoke(job_id):
    """One fixed, operator-confirmed offline test; no provider or GitHub writes."""
    now = datetime.now(timezone.utc)
    submit_verified_task(
        db_path=QUEUE, job_db=JOBS, control_db=STOP, job_id=job_id,
        task="Run approved offline python-unittest smoke; no model calls or GitHub writes",
        now=now)
    queue = DevelopmentTaskQueue(QUEUE)
    if not queue.claim(job_id):
        raise PermissionError("Fresh smoke task claim failed")
    journal = WorkerJournal(JOURNAL)
    try:
        if not journal.record_admission(job_id):
            raise PermissionError("Worker job already admitted")
    finally:
        journal.close()


def admit_held_task(job_id):
    """Promote exactly the approved Slack task, then claim and journal it."""
    promote_held_task(
        held_db="/var/lib/swayzcontrol/held/tasks.db",
        executable_db=QUEUE, job_db=JOBS, stop_db=STOP,
        job_id=job_id, operator_approved=True,
    )
    queue = DevelopmentTaskQueue(QUEUE)
    if not queue.claim(job_id):
        raise PermissionError("Promoted held task claim failed")
    journal = WorkerJournal(JOURNAL)
    try:
        if not journal.record_admission(job_id):
            raise PermissionError("Worker job already admitted")
    finally:
        journal.close()


def require_existing_admission(job_id, *, prepared=False):
    """Resume only an already claimed, once-admitted job; never insert or claim."""
    from agent.persistent_stop_guard import PersistentStopGuard
    PersistentStopGuard(STOP).require_running()
    checks = (
        (QUEUE, "SELECT day_utc,state FROM development_tasks WHERE job_id=?"),
        (JOBS, "SELECT day_utc FROM admitted_jobs WHERE job_id=?"),
        (JOURNAL, "SELECT state FROM worker_jobs WHERE job_id=?"),
    )
    records = []
    for path, query in checks:
        p = Path(path)
        if not p.is_absolute() or p.is_symlink() or not p.is_file():
            raise PermissionError("Existing admission database unavailable")
        with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True) as db:
            rows = db.execute(query, (job_id,)).fetchall()
        if len(rows) != 1:
            raise PermissionError("Job not eligible for one-time admitted recovery")
        records.append(rows[0])
    (queue_day, queue_state), (admitted_day,), (journal_state,) = records
    # Preserve the original admission day across midnight; never mint a new
    # admission, accept mismatched dates, or accept a future-dated record.
    try:
        original_day = datetime.strptime(queue_day, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise PermissionError("Invalid original admission date") from None
    if (queue_state != "claimed" or journal_state != "admitted"
            or admitted_day != queue_day
            or original_day > datetime.now(timezone.utc).date()):
        raise PermissionError("Job not eligible for one-time admitted recovery")
    if not prepared and (Path(INBOX) / (job_id + ".json")).exists():
        raise PermissionError("Existing signed request requires reconciliation")


def validate_prepared_request(job_id, metadata, signing_key):
    """Read-only, fail-closed reconciliation before releasing the stop."""
    p = Path(INBOX) / (job_id + ".json")
    request = protected_json(p, max_bytes=131072)
    if set(request) != {"job_id", "request_id", "provider", "raw_hex", "signature",
                        "expected_manifest", "expected_commit_sha", "snapshot",
                        "snapshot_root", "expected_hashes", "image_digest", "now"}:
        raise PermissionError("Unexpected signed request fields")
    if (request["job_id"] != job_id or request["request_id"] is not None
            or request["provider"] != "none"
            or any(request[k] != metadata[k] for k in (
                "commit_sha", "manifest_sha256", "snapshot", "snapshot_root",
                "expected_hashes", "image_digest") if k in request)):
        raise PermissionError("Signed request does not match approved metadata")
    if (request["expected_commit_sha"] != metadata["commit_sha"]
            or request["expected_manifest"] != metadata["manifest_sha256"]):
        raise PermissionError("Signed request identity mismatch")
    key = Path(signing_key)
    if not key.is_absolute() or key.is_symlink() or not key.is_file():
        raise PermissionError("Signing key missing")
    st = key.stat()
    if st.st_uid != 0 or st.st_mode & 0o077:
        raise PermissionError("Signing key unprotected")
    signed = verify_manifest_job(bytes.fromhex(request["raw_hex"]),
                                 request["signature"], key.read_bytes(),
                                 request["expected_manifest"])
    if signed.job_id != job_id or signed.commit_sha != metadata["commit_sha"]:
        raise PermissionError("Signed request signature identity mismatch")


def validated_snapshot_root(job_id, metadata):
    """Accept legacy metadata only for the exact canonical immutable snapshot."""
    canonical_root = Path("/var/lib/swayz-executor/snapshots")
    canonical_snapshot = canonical_root / job_id
    snapshot = Path(metadata["snapshot"])
    supplied_root = Path(metadata["snapshot_root"])
    if (snapshot != canonical_snapshot or canonical_root.is_symlink()
            or snapshot.is_symlink()
            or supplied_root not in (canonical_root, canonical_snapshot)):
        raise PermissionError("Unexpected snapshot identity")
    return str(canonical_root)


def run(job_id, metadata_path, held_job=False, resume_admitted=False,
        dispatch_prepared=False):
    if os.geteuid() != 0 or not sys.stdin.isatty():
        raise PermissionError("Interactive root operator required")
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", job_id):
        raise ValueError("Invalid job ID")
    if sum(bool(x) for x in (held_job, resume_admitted, dispatch_prepared)) > 1:
        raise PermissionError("Conflicting execution modes")
    config = protected_json(CONFIG)
    metadata = protected_json(metadata_path, max_bytes=131072)
    if set(metadata) != {"job_id","commit_sha","manifest_sha256","snapshot",
                         "snapshot_root","expected_hashes","image_digest"}:
        raise PermissionError("Unexpected job metadata")
    if metadata["job_id"] != job_id:
        raise PermissionError("Job identity mismatch")
    snapshot_root = validated_snapshot_root(job_id, metadata)
    # Verify the immutable approved snapshot BEFORE consuming a job slot.
    verify_snapshot_before_execution(metadata["snapshot"], metadata["expected_hashes"])
    if set(config) != {"job_db","budget_db","signing_key_file","approved_image_digests"}:
        raise PermissionError("Executor configuration incompatible")
    if config["job_db"] != JOBS or config["signing_key_file"] != KEY:
        raise PermissionError("Unexpected authoritative executor paths")
    if dispatch_prepared:
        # Reconcile once before operator authorisation; do not re-admit or re-sign.
        validate_prepared_request(job_id, metadata, KEY)
    if input("Type AUTHORISE " + job_id + " to open a supervised window: ") != "AUTHORISE " + job_id:
        raise PermissionError("Operator confirmation required")
    stop = EmergencyStop(STOP)
    try:
        if not stop.is_stopped():
            raise PermissionError("Stop must initially be engaged")
    finally:
        stop.close()
    # Recovery timer is installed before any stop release, survives this
    # process, and invokes only the pinned protected deployment entrypoint.
    script = Path(__file__).resolve()
    if script.is_symlink() or script.stat().st_uid != 0 or script.stat().st_mode & 0o022:
        raise PermissionError("Deployment script must be root-owned and protected")
    # Executor adapter can wait up to 360 seconds. The recovery timer must
    # outlive that bounded attempt plus cleanup and service restoration.
    cmd("systemd-run", "--unit=swayz-activation-recover-" + job_id,
        "--on-active=480s", sys.executable, str(script), "--recover")
    try:
        cmd("systemctl", "stop", CONTROL)
        stop = EmergencyStop(STOP)
        try:
            stop.enable(owner_authorised=True)
        finally:
            stop.close()
        # Admit exactly once, inside the authorised window. The existing
        # 20-job quota is consumed by submit_verified_task, not twice.
        if dispatch_prepared:
            require_existing_admission(job_id, prepared=True)
        elif resume_admitted:
            require_existing_admission(job_id)
        elif held_job:
            admit_held_task(job_id)
        else:
            admit_supervised_smoke(job_id)
        if dispatch_prepared:
            result = dispatch_prepared_offline_job(
                job_id=job_id, snapshot=metadata["snapshot"],
                snapshot_root=snapshot_root,
                expected_hashes=metadata["expected_hashes"],
                signing_key_path=KEY, stop_db=STOP)
        else:
            result = run_one_supervised_handoff(
            job_id=job_id, commit_sha=metadata["commit_sha"],
            manifest_sha256=metadata["manifest_sha256"],
            snapshot=metadata["snapshot"], snapshot_root=snapshot_root,
            expected_hashes=metadata["expected_hashes"],
            image_digest=metadata["image_digest"],
            approved_images=frozenset(config["approved_image_digests"]),
            queue_db=QUEUE, job_db=JOBS, journal_db=JOURNAL,
            stop_db=STOP, signing_key_file=KEY, request_directory=INBOX)
        if result != {"state":"passed","cleanup_verified":True}:
            raise RuntimeError("Supervised job did not pass with cleanup")
        return result
    finally:
        restore()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recover", action="store_true")
    parser.add_argument("--job")
    parser.add_argument("--metadata")
    parser.add_argument("--dispatch-prepared", action="store_true",
                        help="Dispatch existing signed request without re-admission or signing")
    parser.add_argument("--resume-admitted", action="store_true",
                        help="Execute existing claimed admission without re-admitting")
    parser.add_argument("--held-job", action="store_true",
                        help="Promote the existing held Slack job instead of staging a smoke task")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    if args.recover:
        if args.job or args.metadata or args.held_job or args.resume_admitted or args.dispatch_prepared:
            parser.error("Recovery accepts no job arguments")
        restore()
    else:
        if not args.job or not args.metadata:
            parser.error("Job and protected metadata required")
        print(json.dumps(run(args.job, args.metadata, held_job=args.held_job,
                             resume_admitted=args.resume_admitted,
                             dispatch_prepared=args.dispatch_prepared)))


if __name__ == "__main__":
    main()
