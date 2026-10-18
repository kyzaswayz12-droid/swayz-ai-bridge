"""Offline worker identity binding check.

The signed envelope's job ID and commit SHA must match independently
observed checkout identity. No Docker, network or Git calls occur here.
"""
from dataclasses import dataclass
from .signed_handoff import verify_manifest_job


@dataclass(frozen=True)
class VerifiedWorkerIdentity:
    job_id: str
    commit_sha: str
    repository: str
    suite: str


def verify_worker_identity(*, raw, signature, secret, manifest_sha256,
                           expected_job_id, observed_commit_sha):
    job = verify_manifest_job(raw, signature, secret, manifest_sha256)
    if job.job_id != expected_job_id:
        raise PermissionError("Signed job identity mismatch")
    if job.commit_sha != observed_commit_sha:
        raise PermissionError("Signed source commit mismatch")
    return VerifiedWorkerIdentity(job.job_id, job.commit_sha,
                                  job.repository, job.suite)
