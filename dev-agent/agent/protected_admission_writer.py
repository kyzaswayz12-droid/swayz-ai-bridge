"""Operator-controlled protected admission record writer.

Only an independently authenticated root operator may invoke this boundary.
Never accepts arbitrary state paths, signing keys or image allowlists from an
AI worker. The existing signer independently rechecks all ledgers and hashes.
This does not sign, start Docker or release the emergency stop.
"""
import json
import os
import re
import stat
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .persistent_stop_guard import PersistentStopGuard
from .snapshot_reverification import verify_snapshot_before_execution

_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SHA = re.compile(r"^[a-f0-9]{40}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
ROOT = Path("/var/lib/swayz-executor")
METADATA = ROOT / "admission-metadata"
SNAPSHOTS = ROOT / "snapshots"
QUEUE_DB = "/var/lib/swayzcontrol/state/development_tasks.db"
JOB_DB = str(ROOT / "jobs.sqlite3")
JOURNAL_DB = "/var/lib/swayzcontrol/state/journal.db"
STOP_DB = "/var/lib/swayzcontrol/state/stop.db"
REQUESTS = str(ROOT / "requests")


def write_protected_admission(*, job_id, commit_sha, proposal_sha256,
                              manifest_sha256, expected_hashes,
                              image_digest, approved_images,
                              signing_key_file, require_operator):
    if os.geteuid() != 0 or not callable(require_operator):
        raise PermissionError("Independent privileged operator required")
    if require_operator(job_id=job_id) is not True:
        raise PermissionError("Operator approval missing")
    if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise PermissionError("Invalid job ID")
    if not isinstance(commit_sha, str) or not _SHA.fullmatch(commit_sha):
        raise PermissionError("Invalid commit SHA")
    if any(not isinstance(x, str) or not _HASH.fullmatch(x)
           for x in (proposal_sha256, manifest_sha256)):
        raise PermissionError("Invalid proposal or manifest digest")
    if (not isinstance(expected_hashes, dict) or not expected_hashes
            or any(not isinstance(k, str) or not k or k.startswith("/")
                   or ".." in k.split("/") or not isinstance(v, str)
                   or not _HASH.fullmatch(v)
                   for k,v in expected_hashes.items())):
        raise PermissionError("Invalid snapshot manifest")
    if (not isinstance(approved_images, frozenset) or
            image_digest not in approved_images or
            not isinstance(image_digest, str) or
            not image_digest.startswith("sha256:") or
            not _HASH.fullmatch(image_digest[7:])):
        raise PermissionError("Image not independently approved")
    if signing_key_file != "/etc/swayz/executor-signing.key":
        raise PermissionError("Unexpected signing key path")
    # Prepare immutable metadata WHILE stopped. The signer separately checks
    # the released stop during the supervised execution window.
    guard = PersistentStopGuard(STOP_DB)
    try:
        guard.require_running()
    except PermissionError:
        pass
    else:
        raise PermissionError("Admission preparation requires engaged stop")
    day = datetime.now(timezone.utc).date().isoformat()
    with sqlite3.connect("file:" + QUEUE_DB + "?mode=ro", uri=True) as db:
        queued = db.execute("SELECT day_utc,state FROM development_tasks WHERE job_id=?",
                            (job_id,)).fetchall()
    with sqlite3.connect("file:" + JOB_DB + "?mode=ro", uri=True) as db:
        admitted = db.execute("SELECT day_utc FROM admitted_jobs WHERE job_id=?",
                              (job_id,)).fetchall()
        count = db.execute("SELECT COUNT(*) FROM admitted_jobs WHERE day_utc=?",
                           (day,)).fetchone()[0]
    with sqlite3.connect("file:" + JOURNAL_DB + "?mode=ro", uri=True) as db:
        journal = db.execute("SELECT state FROM worker_jobs WHERE job_id=?",
                             (job_id,)).fetchall()
    if (queued != [(day, "claimed")] or admitted != [(day,)]
            or journal != [("admitted",)] or not 1 <= count <= 20):
        raise PermissionError("Fresh claimed admission and unused journal required")
    snapshot = SNAPSHOTS / job_id
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise PermissionError("Missing protected snapshot")
    verify_snapshot_before_execution(str(snapshot), expected_hashes)
    st = METADATA.stat()
    if METADATA.is_symlink() or not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077:
        raise PermissionError("Unprotected admission directory")
    record = {
        "job_id":job_id,"commit_sha":commit_sha,
        "proposal_sha256":proposal_sha256,
        "manifest_sha256":manifest_sha256,
        "snapshot":str(snapshot),"snapshot_root":str(SNAPSHOTS),
        "expected_hashes":expected_hashes,"image_digest":image_digest,
        "approved_images":sorted(approved_images),
        "queue_db":QUEUE_DB,"job_db":JOB_DB,"journal_db":JOURNAL_DB,
        "stop_db":STOP_DB,"signing_key_file":signing_key_file,
        "request_directory":REQUESTS}
    payload=json.dumps(record,sort_keys=True,separators=(",",":")).encode()
    if len(payload)>65536:
        raise PermissionError("Oversized admission metadata")
    try:
        guard.require_running()
    except PermissionError:
        pass
    else:
        raise PermissionError("Stop released during metadata preparation")
    target=METADATA / (job_id+".json")
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return str(target)
