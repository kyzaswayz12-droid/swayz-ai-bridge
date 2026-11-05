#!/usr/bin/env python3
"""One explicitly authorised supervised Swayz handoff. NOT unattended autonomy.

Run only from a reviewed, root-owned immutable deployment. Never run this
entrypoint from a writable Git checkout. Recovery is independent of the job.
"""
import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from agent.emergency_stop import EmergencyStop
from agent.one_shot_activation import run_one_supervised_handoff

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


def protected_json(path):
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise PermissionError("Protected input missing")
    st = p.stat()
    if st.st_uid != 0 or st.st_mode & 0o077 or not stat.S_ISREG(st.st_mode) or st.st_size > 32768:
        raise PermissionError("Unprotected input")
    return json.loads(p.read_text())


def run(job_id, metadata_path):
    if os.geteuid() != 0 or not sys.stdin.isatty():
        raise PermissionError("Interactive root operator required")
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", job_id):
        raise ValueError("Invalid job ID")
    config = protected_json(CONFIG)
    metadata = protected_json(metadata_path)
    if set(metadata) != {"job_id","commit_sha","manifest_sha256","snapshot",
                         "snapshot_root","expected_hashes","image_digest"}:
        raise PermissionError("Unexpected job metadata")
    if metadata["job_id"] != job_id:
        raise PermissionError("Job identity mismatch")
    if set(config) != {"job_db","budget_db","signing_key_file","approved_image_digests"}:
        raise PermissionError("Executor configuration incompatible")
    if config["job_db"] != JOBS or config["signing_key_file"] != KEY:
        raise PermissionError("Unexpected authoritative executor paths")
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
    cmd("systemd-run", "--unit=swayz-activation-recover-" + job_id,
        "--on-active=120s", sys.executable, str(script), "--recover")
    try:
        cmd("systemctl", "stop", CONTROL)
        stop = EmergencyStop(STOP)
        try:
            stop.enable(owner_authorised=True)
        finally:
            stop.close()
        result = run_one_supervised_handoff(
            job_id=job_id, commit_sha=metadata["commit_sha"],
            manifest_sha256=metadata["manifest_sha256"],
            snapshot=metadata["snapshot"], snapshot_root=metadata["snapshot_root"],
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
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    if args.recover:
        if args.job or args.metadata:
            parser.error("Recovery accepts no job arguments")
        restore()
    else:
        if not args.job or not args.metadata:
            parser.error("Job and protected metadata required")
        print(json.dumps(run(args.job, args.metadata)))


if __name__ == "__main__":
    main()
