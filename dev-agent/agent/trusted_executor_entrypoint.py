"""Explicit one-shot local operator entrypoint for the trusted Docker worker.

No network listener, background scheduler, or autonomous activation.
Requires a root-owned protected configuration and request file. Never accept
control paths, signing keys, or Docker commands from an untrusted job payload.
"""
import argparse
import json
import os
import stat
import re
from datetime import datetime
from pathlib import Path

from .local_supervised_worker_service import run_operator_supervised_worker
from .executor_ledger_compatibility import verify_executor_ledger

CONFIG = Path("/etc/swayz/trusted-executor.json")
STOP = "/var/lib/swayzcontrol/state/stop.db"
JOURNAL = "/var/lib/swayzcontrol/state/journal.db"
REPO = "kyzaswayz12-droid/swayz-ai-bridge"


def _protected_json(path):
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise PermissionError("Protected file missing or unsafe")
    info = p.stat()
    if info.st_uid != 0 or info.st_mode & 0o077 or not stat.S_ISREG(info.st_mode):
        raise PermissionError("File must be root-owned and mode 0600 or stricter")
    if info.st_size > 32768:
        raise PermissionError("Protected file too large")
    value = json.loads(p.read_text())
    if not isinstance(value, dict):
        raise PermissionError("Invalid protected file")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--supervised-once", action="store_true")
    parser.add_argument("--request", required=True)
    args = parser.parse_args(argv)
    if os.geteuid() != 0 or not args.supervised_once:
        raise PermissionError("Explicit root operator supervision required")
    config = _protected_json(CONFIG)
    request_path = Path(args.request)
    if (request_path.parent != Path("/var/lib/swayz-executor/requests")
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}\\.json", request_path.name)):
        raise PermissionError("Request must use the protected job inbox")
    request = _protected_json(args.request)
    if request.get("job_id") != request_path.stem:
        raise PermissionError("Request job identity does not match inbox filename")
    if set(config) != {"job_db", "budget_db", "signing_key_file", "approved_image_digests"}:
        raise PermissionError("Invalid executor configuration")
    verify_executor_ledger(config["job_db"], "job")
    verify_executor_ledger(config["budget_db"], "budget")
    if set(request) != {"job_id", "request_id", "provider", "raw_hex", "signature",
                        "expected_manifest", "expected_commit_sha", "snapshot",
                        "snapshot_root", "expected_hashes", "image_digest", "now"}:
        raise PermissionError("Invalid supervised request")
    key_path = Path(config["signing_key_file"])
    if key_path.is_symlink() or not key_path.is_file():
        raise PermissionError("Signing key missing")
    key_stat = key_path.stat()
    if key_stat.st_uid != 0 or key_stat.st_mode & 0o077 or key_stat.st_size < 32 or key_stat.st_size > 4096:
        raise PermissionError("Signing key permissions invalid")
    secret = key_path.read_bytes()
    if len(secret) < 32:
        raise PermissionError("Signing key too short")
    if not isinstance(config["approved_image_digests"], list):
        raise PermissionError("Invalid approved image list")
    result = run_operator_supervised_worker(
        job_id=request["job_id"], journal_path=JOURNAL,
        server_control_db=STOP, job_db=config["job_db"],
        budget_db=config["budget_db"], request_id=request["request_id"],
        provider=request["provider"], now=datetime.fromisoformat(request["now"]),
        raw=bytes.fromhex(request["raw_hex"]), signature=request["signature"],
        secret=secret, expected_manifest=request["expected_manifest"],
        expected_repository=REPO, expected_commit_sha=request["expected_commit_sha"],
        snapshot=request["snapshot"], snapshot_root=request["snapshot_root"],
        expected_hashes=request["expected_hashes"],
        image_digest=request["image_digest"],
        approved_image_digests=frozenset(config["approved_image_digests"]),
    )
    print(json.dumps({"job_id": result.job_id, "state": result.state,
                      "cleanup_verified": result.cleanup_verified}))
    if result.state != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
