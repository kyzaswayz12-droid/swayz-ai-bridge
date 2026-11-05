"""Operator-controlled preparation of an offline signed executor request.

This is NOT an autonomous daemon. It cannot start systemd, Docker, models,
or GitHub. The caller must be the independently authenticated privileged
operator; the untrusted queue never receives the signing key.
"""
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .persistent_stop_guard import PersistentStopGuard
from .snapshot_reverification import verify_snapshot_before_execution
from .signed_handoff import sign_manifest_job
from .test_jobs import TestJob

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_REPO = "kyzaswayz12-droid/swayz-ai-bridge"


def prepare_offline_executor_request(*, job_id, commit_sha, manifest_sha256,
                                     snapshot, snapshot_root, expected_hashes,
                                     image_digest, approved_images, queue_db,
                                     job_db, journal_db, stop_db, signing_key_file,
                                     request_directory, now=None):
    """Prepare one root-protected request; never start or authorise execution."""
    if os.geteuid() != 0:
        raise PermissionError("Privileged operator required")
    if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
        raise ValueError("Invalid job ID")
    if not isinstance(approved_images, frozenset) or image_digest not in approved_images:
        raise PermissionError("Image not independently approved")
    guard = PersistentStopGuard(stop_db)
    guard.require_running()
    root, snap = Path(snapshot_root), Path(snapshot)
    if not root.is_absolute() or root.is_symlink() or snap != root / job_id:
        raise PermissionError("Unexpected snapshot path")
    verify_snapshot_before_execution(str(snap), expected_hashes)
    day = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date().isoformat()
    for path in (queue_db, job_db, journal_db):
        p = Path(path)
        if not p.is_absolute() or p.is_symlink() or not p.is_file():
            raise PermissionError("Required state unavailable")
    with sqlite3.connect(Path(queue_db).as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute("SELECT day_utc,state FROM development_tasks WHERE job_id=?", (job_id,)).fetchall()
    if rows != [(day, "claimed")]:
        raise PermissionError("Claimed task missing or expired")
    with sqlite3.connect(Path(job_db).as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute("SELECT day_utc FROM admitted_jobs WHERE job_id=?", (job_id,)).fetchall()
        count = db.execute("SELECT COUNT(*) FROM admitted_jobs WHERE day_utc=?", (day,)).fetchone()[0]
    if rows != [(day,)] or not 1 <= count <= 20:
        raise PermissionError("Admission quota mismatch")
    with sqlite3.connect(Path(journal_db).as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute("SELECT state FROM worker_jobs WHERE job_id=?", (job_id,)).fetchall()
    if rows != [("admitted",)]:
        raise PermissionError("Journal admission missing or already used")
    key = Path(signing_key_file)
    if not key.is_absolute() or key.is_symlink() or not key.is_file():
        raise PermissionError("Signing key unavailable")
    st = key.stat()
    if st.st_uid != 0 or st.st_mode & 0o077:
        raise PermissionError("Signing key must be root-owned and private")
    secret = key.read_bytes()
    raw, signature = sign_manifest_job(
        TestJob(job_id, _REPO, commit_sha, "python-unittest"),
        manifest_sha256, secret)
    inbox = Path(request_directory)
    if not inbox.is_absolute() or inbox.is_symlink() or not inbox.is_dir():
        raise PermissionError("Protected request directory missing")
    info = inbox.stat()
    if info.st_uid != 0 or info.st_mode & 0o077:
        raise PermissionError("Request directory must be root-owned and private")
    request = {
        "job_id": job_id, "request_id": None, "provider": "none",
        "raw_hex": raw.hex(), "signature": signature,
        "expected_manifest": manifest_sha256,
        "expected_commit_sha": commit_sha,
        "snapshot": str(snap), "snapshot_root": str(root),
        "expected_hashes": expected_hashes, "image_digest": image_digest,
        "now": (now or datetime.now(timezone.utc)).isoformat(),
    }
    payload = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    guard.require_running()
    target = inbox / (job_id + ".json")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return str(target)
