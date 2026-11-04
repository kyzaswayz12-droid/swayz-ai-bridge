"""Bridge generated snapshots to the existing one-shot systemd executor.

A separately authorised operator must prepare the root-owned signed request,
admit the job, and open a supervised execution window. This adapter cannot
sign jobs, release the emergency stop, or start unattended execution.
"""
import json
import re
import subprocess
from pathlib import Path
from .signed_handoff import verify_manifest_job
from .snapshot_reverification import verify_snapshot_before_execution

_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
REQUESTS = Path("/var/lib/swayz-executor/requests")
UNIT = "swayz-trusted-executor@{}.service"


def run_prepared_generated_job(*, job_id, snapshot, snapshot_root,
                               expected_hashes, signing_key_path,
                               require_running, systemctl=subprocess.run):
    if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise ValueError("Invalid job ID")
    if not callable(require_running):
        raise PermissionError("Authoritative stop check required")
    root, snap = Path(snapshot_root), Path(snapshot)
    if snap != root / job_id or not root.is_absolute():
        raise PermissionError("Unexpected snapshot")
    verify_snapshot_before_execution(snap, expected_hashes)
    path = REQUESTS / (job_id + ".json")
    if path.is_symlink() or not path.is_file():
        raise PermissionError("Signed job request missing")
    info = path.stat()
    if info.st_uid != 0 or info.st_mode & 0o077:
        raise PermissionError("Unprotected signed request")
    request = json.loads(path.read_text())
    if (request.get("job_id") != job_id
            or request.get("provider") != "none"
            or request.get("request_id") is not None
            or request.get("snapshot") != str(snap)
            or request.get("snapshot_root") != str(root)
            or request.get("expected_hashes") != expected_hashes):
        raise PermissionError("Request does not bind generated snapshot")
    key = Path(signing_key_path)
    if key.is_symlink() or not key.is_file() or key.stat().st_uid != 0 or key.stat().st_mode & 0o077:
        raise PermissionError("Unprotected signing key")
    signed = verify_manifest_job(
        bytes.fromhex(request["raw_hex"]), request["signature"],
        key.read_bytes(), request["expected_manifest"])
    if signed.job_id != job_id or signed.commit_sha != request["expected_commit_sha"]:
        raise PermissionError("Signed job identity mismatch")
    require_running()
    unit = UNIT.format(job_id)
    result = systemctl(["systemctl", "start", unit],
                       capture_output=True, text=True, timeout=360, check=False)
    # The authoritative journal must be queried independently; systemctl
    # exit status alone is not evidence of Docker cleanup or test success.
    from .worker_journal import WorkerJournal
    journal = WorkerJournal("/var/lib/swayzcontrol/state/journal.db")
    try:
        record = journal.status(job_id)
    finally:
        journal.close()
    passed = result.returncode == 0 and record is not None and record[0] == "passed"
    return {"state": "passed" if passed else "blocked",
            "cleanup_verified": passed}
