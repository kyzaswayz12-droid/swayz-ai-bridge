"""Ed25519 authenticated job admission with durable replay protection.

The public key must be provisioned by a trusted administrator. This module
does not run Docker, sign requests or grant job execution privileges.
"""
import sqlite3
import time
from .ed25519_handoff import verify_job_ed25519
from .test_jobs import TestJob
from .test_jobs import _ID, _SHA


def accept_ed25519_job(inbox, raw, signature, public_key, *,
                       expected_repository, expected_manifest):
    payload = verify_job_ed25519(raw, signature, public_key)
    job = TestJob(payload["job_id"], payload["repository"],
                  payload["commit_sha"], payload["suite"])
    if job.repository != expected_repository:
        raise PermissionError("Unexpected repository")
    if payload["manifest_sha256"] != expected_manifest:
        raise PermissionError("Manifest mismatch")
    if not _ID.fullmatch(job.job_id) or not _SHA.fullmatch(job.commit_sha):
        raise PermissionError("Invalid job identity")
    inbox.db.execute("BEGIN IMMEDIATE")
    try:
        result = inbox.db.execute(
            "INSERT OR IGNORE INTO accepted_jobs VALUES(?,?,?,?)",
            (job.job_id, job.commit_sha, "accepted", int(time.time())))
        inbox.db.execute("COMMIT")
        return result.rowcount == 1
    except BaseException:
        inbox.db.execute("ROLLBACK")
        raise
