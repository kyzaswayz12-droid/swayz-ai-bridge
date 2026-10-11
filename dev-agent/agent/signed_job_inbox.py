"""Admit manifest-authenticated jobs using durable replay protection.

No Docker execution. Caller must independently recompute expected manifest
from trusted workspace before admission.
"""
import time
from .signed_handoff import verify_manifest_job
from .job_inbox import JobInbox

def admit_signed_handoff(inbox: JobInbox, raw: bytes, signature: str,
                         secret: bytes, expected_manifest: str) -> bool:
    job=verify_manifest_job(raw,signature,secret,expected_manifest)
    inbox.db.execute("BEGIN IMMEDIATE")
    try:
        cursor=inbox.db.execute(
            "INSERT OR IGNORE INTO accepted_jobs VALUES(?,?,?,?)",
            (job.job_id,job.commit_sha,"accepted",int(time.time())))
        inbox.db.execute("COMMIT")
        return cursor.rowcount==1
    except BaseException:
        inbox.db.execute("ROLLBACK")
        raise
