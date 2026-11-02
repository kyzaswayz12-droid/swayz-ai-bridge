"""Version 2 Ed25519 admission with image, manifest and commit binding.

This module does not execute Docker or provision keys. The trusted worker
must supply its independently attested checkout SHA and approved image digest.
"""
import time
from .ed25519_worker_envelope_v2 import verify_worker_envelope_v2
from .test_jobs import TestJob, serialize_job


def admit_worker_envelope_v2(inbox, raw, signature, public_key, *,
                             expected_manifest, expected_commit,
                             expected_image_digest, approved_image_digests):
    if not isinstance(approved_image_digests, frozenset) or expected_image_digest not in approved_image_digests:
        raise PermissionError("Image not allowlisted")
    payload = verify_worker_envelope_v2(
        raw, signature, public_key, expected_image_digest=expected_image_digest)
    if payload["manifest_sha256"] != expected_manifest:
        raise PermissionError("Signed manifest mismatch")
    if payload["commit_sha"] != expected_commit:
        raise PermissionError("Signed commit mismatch")
    job = TestJob(payload["job_id"], payload["repository"],
                  payload["commit_sha"], payload["suite"])
    serialize_job(job)
    inbox.db.execute("BEGIN IMMEDIATE")
    try:
        cursor = inbox.db.execute(
            "INSERT OR IGNORE INTO accepted_jobs VALUES(?,?,?,?)",
            (job.job_id, job.commit_sha, "accepted", int(time.time())))
        inbox.db.execute("COMMIT")
        return cursor.rowcount == 1
    except BaseException:
        inbox.db.execute("ROLLBACK")
        raise
