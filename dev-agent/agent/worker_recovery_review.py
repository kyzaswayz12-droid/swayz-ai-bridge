"""Offline recovery decisions for interrupted worker lifecycles.

No Docker, database writes, or process execution. A privileged service must
perform cleanup and independently verify the exact container identity before
making any recovery transition.
"""
from dataclasses import dataclass
from .cleanup_evidence import cleanup_evidence_verified


@dataclass(frozen=True)
class RecoveryDecision:
    job_id: str
    state: str
    cleanup_verified: bool
    execution_allowed: bool = False


def review_worker_recovery(*, job_id: str, journal_state: str,
                           inspect_exit_code: int, inspect_stderr: str,
                           daemon_healthy: bool):
    if not isinstance(job_id, str) or not job_id or len(job_id) > 64:
        raise PermissionError("Invalid recovery job")
    if journal_state not in ("admitted", "running", "blocked"):
        raise PermissionError("Unexpected recovery state")
    name = "swayz-test-" + job_id
    clean = cleanup_evidence_verified(
        container_name=name, inspect_exit_code=inspect_exit_code,
        inspect_stderr=inspect_stderr, daemon_healthy=daemon_healthy)
    return RecoveryDecision(job_id, "blocked", clean)
