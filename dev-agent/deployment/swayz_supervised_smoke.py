#!/usr/bin/env python3
"""One explicitly supervised, no-provider Swayz smoke attempt. Not a scheduler."""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

DB = "/var/lib/swayzcontrol/state/stop.db"
CONTROL = "swayz-worker-control.service"


def stop_state(value):
    db = sqlite3.connect(DB, timeout=10)
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchone()
        if row not in ((0,), (1,)):
            raise RuntimeError("Invalid emergency stop")
        if value == 0 and row != (1,):
            raise RuntimeError("Stop must be engaged before supervised release")
        updated = db.execute("UPDATE agent_control SET stopped=? WHERE id=1", (value,))
        if updated.rowcount != 1:
            raise RuntimeError("Stop update failed")
        db.commit()
    finally:
        db.close()


def recover():
    # Always restore the stop BEFORE allowing the control service to restart.
    stop_state(1)
    subprocess.run(["systemctl", "start", CONTROL], check=True)


def run(job_id):
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    import re
    if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", job_id):
        raise ValueError("Invalid job ID")
    unit = f"swayz-trusted-executor@{job_id}.service"
    request = Path(f"/var/lib/swayz-executor/requests/{job_id}.json")
    if request.is_symlink() or not request.is_file() or request.stat().st_uid != 0 or request.stat().st_mode & 0o077:
        raise PermissionError("Protected signed request required")
    req = json.loads(request.read_text())
    if req.get("job_id") != job_id or req.get("provider") != "none" or req.get("request_id") is not None:
        raise PermissionError("Only the signed zero-provider smoke job is allowed")
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as db:
        if db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchone() != (1,):
            raise PermissionError("Emergency stop must start engaged")
    # Independent systemd watchdog survives the operator process exiting.
    subprocess.run([
        "systemd-run", "--unit=swayz-smoke-watchdog", "--on-active=150s",
        sys.executable, str(Path(__file__).resolve()), "--recover"
    ], check=True)
    try:
        subprocess.run(["systemctl", "stop", CONTROL], check=True, timeout=15)
        stop_state(0)
        subprocess.run(["systemctl", "reset-failed", unit], check=True)
        try:
            result = subprocess.run(["systemctl", "start", unit], timeout=90)
            print("SWAYZ_EXECUTOR_EXIT", result.returncode, flush=True)
        except subprocess.TimeoutExpired:
            print("SWAYZ_EXECUTOR_TIMEOUT", flush=True)
            subprocess.run(["systemctl", "stop", unit], timeout=20, check=False)
    finally:
        recover()
    subprocess.run(["systemctl", "show", unit, "-p", "Result", "-p", "ExecMainStatus", "--no-pager"])
    subprocess.run(["journalctl", "-u", unit, "-n", "25", "--no-pager"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--recover", action="store_true")
    parser.add_argument("--job", help="Fresh, pre-admitted, protected signed job ID")
    args = parser.parse_args()
    if args.recover:
        if os.geteuid() != 0:
            raise PermissionError("Root recovery required")
        recover()
    else:
        if not args.job:
            parser.error("--job is required for supervised execution")
        run(args.job)
