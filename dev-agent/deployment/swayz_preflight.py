"""Read-only, fail-closed preflight for an existing supervised offline Swayz job.

Never admits, signs, dispatches, transitions journal state or changes emergency stop.
A PASS is NOT permission to execute; the supervised entrypoint must recheck all gates.
"""
import argparse
import json
import os
import re
import sqlite3
import stat
from pathlib import Path
from datetime import datetime, timezone

from agent.snapshot_reverification import verify_snapshot_before_execution
from deployment import swayz_one_shot_window as window

JOB_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def _read_rows(path, sql, job_id=None):
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise PermissionError("Ledger path missing or unsafe")
    with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        return db.execute(sql, () if job_id is None else (job_id,)).fetchall()


def inspect(job_id, *, paths=None):
    """Return diagnostic statuses; never mutate on failure or success.

    Paths can be injected by isolated unit tests only. The CLI always uses
    authoritative paths and does not accept path overrides.
    """
    if not isinstance(job_id, str) or not JOB_PATTERN.fullmatch(job_id):
        raise ValueError("Invalid job ID")
    p = paths or {
        "jobs": window.JOBS, "queue": window.QUEUE,
        "journal": window.JOURNAL, "stop": window.STOP,
        "metadata": "/var/lib/swayz-executor/" + job_id + ".metadata.json",
        "config": window.CONFIG, "key": window.KEY,
        "inbox": window.INBOX,
    }
    result = {"job_id": job_id, "checks": {}, "execution_authorised": False}
    checks = result["checks"]

    def check(name, callback):
        try:
            callback()
        except (OSError, sqlite3.Error, PermissionError, ValueError, TypeError,
                KeyError, json.JSONDecodeError) as exc:
            checks[name] = "FAIL"
            # Never print credentials or raw signed payloads.
            result.setdefault("failures", []).append(name + ": " + type(exc).__name__)
        else:
            checks[name] = "PASS"

    data = {}

    def admission():
        rows = _read_rows(p["jobs"],
            "SELECT day_utc FROM admitted_jobs WHERE job_id=?", job_id)
        if len(rows) != 1:
            raise PermissionError("Admission absent or duplicated")
        day = rows[0][0]
        original = datetime.strptime(day, "%Y-%m-%d").date()
        if original.isoformat() != day or original > datetime.now(timezone.utc).date():
            raise PermissionError("Invalid admission date")
        data["day"] = day
        result["original_admission"] = day

    def queue():
        if _read_rows(p["queue"],
                "SELECT day_utc,state FROM development_tasks WHERE job_id=?", job_id) != [
                    (data["day"], "claimed")]:
            raise PermissionError("Original queue claim mismatch")

    def journal():
        if _read_rows(p["journal"],
                "SELECT state FROM worker_jobs WHERE job_id=?", job_id) != [("admitted",)]:
            raise PermissionError("Journal not admitted")

    def quota():
        rows = _read_rows(p["jobs"],
            "SELECT COUNT(*) FROM admitted_jobs WHERE day_utc=?", data["day"])
        if len(rows) != 1 or not 1 <= rows[0][0] <= 20:
            raise PermissionError("Daily quota invalid")

    def signature():
        metadata = window.protected_json(p["metadata"], max_bytes=131072)
        config = window.protected_json(p["config"])
        if (metadata["job_id"] != job_id
                or config["job_db"] != p["jobs"]
                or config["signing_key_file"] != p["key"]):
            raise PermissionError("Protected configuration identity mismatch")
        # Production verifier reads the protected existing request and signing
        # key; no request creation or key output.
        window.validate_prepared_request(job_id, metadata, p["key"])
        data["metadata"] = metadata

    def snapshot():
        metadata = data["metadata"]
        # The canonical snapshot identity is pinned by the same production
        # helper used by the supervised recovery script.
        if paths is None:
            window.validated_snapshot_root(job_id, metadata)
        verify_snapshot_before_execution(metadata["snapshot"], metadata["expected_hashes"])

    def stop():
        rows = _read_rows(p["stop"], "SELECT stopped FROM agent_control WHERE id=1")
        if rows != [(1,)]:
            raise PermissionError("Emergency stop not engaged")

    def access():
        # Check authoritative directory and file metadata but do not change it.
        for k in ("jobs", "queue", "journal", "stop"):
            f = Path(p[k])
            if not f.is_file() or f.is_symlink():
                raise PermissionError("Ledger missing or unsafe")
            if not stat.S_ISREG(f.stat().st_mode):
                raise PermissionError("Ledger not regular")
        # Access here is the invoking process's access, not a guarantee about
        # a later systemd sandbox.
        _read_rows(p["queue"],
            "SELECT day_utc FROM development_tasks WHERE job_id=?", job_id)

    for name, action, prerequisites in (
        ("original_admission", admission, ()),
        ("queue_claim", queue, ("original_admission",)),
        ("journal", journal, ()),
        ("daily_quota", quota, ("original_admission",)),
        ("signed_request", signature, ()),
        ("snapshot_integrity", snapshot, ("signed_request",)),
        ("ledger_readability", access, ()),
        ("emergency_stop_engaged", stop, ()),
    ):
        if all(checks.get(required) == "PASS" for required in prerequisites):
            check(name, action)
        else:
            checks[name] = "BLOCKED"
    result["state"] = ("READY_FOR_SUPERVISED_REVIEW"
                       if all(v == "PASS" for v in checks.values())
                       else "BLOCKED")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only supervised job preflight; never executes.")
    parser.add_argument("--job", required=True)
    args = parser.parse_args(argv)
    result = inspect(args.job)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "READY_FOR_SUPERVISED_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
