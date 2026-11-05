#!/usr/bin/env python3
"""One explicitly supervised, no-provider Swayz smoke attempt. Not a scheduler."""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

JOB = "swayztest001"
DB = "/var/lib/swayzcontrol/state/stop.db"
UNIT = f"swayz-trusted-executor@{JOB}.service"
CONTROL = "swayz-worker-control.service"
REQUEST = Path(f"/var/lib/swayz-executor/requests/{JOB}.json")
OVERRIDE = Path("/etc/systemd/system/swayz-trusted-executor@.service.d/access.conf")


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


def run():
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    req = json.loads(REQUEST.read_text())
    if req.get("job_id") != JOB or req.get("provider") != "none" or req.get("request_id") is not None:
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
        subprocess.run(["systemctl", "reset-failed", UNIT], check=True)
        try:
            result = subprocess.run(["systemctl", "start", UNIT], timeout=90)
            print("SWAYZ_EXECUTOR_EXIT", result.returncode, flush=True)
        except subprocess.TimeoutExpired:
            print("SWAYZ_EXECUTOR_TIMEOUT", flush=True)
            subprocess.run(["systemctl", "stop", UNIT], timeout=20, check=False)
    finally:
        # Do not leave the temporary DAC capability override installed.
        try:
            recover()
        finally:
            if OVERRIDE.is_file() and not OVERRIDE.is_symlink():
                OVERRIDE.unlink()
                subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "show", UNIT, "-p", "Result", "-p", "ExecMainStatus", "--no-pager"])
    subprocess.run(["journalctl", "-u", UNIT, "-n", "25", "--no-pager"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    if args.recover:
        if os.geteuid() != 0:
            raise PermissionError("Root recovery required")
        recover()
    else:
        run()
