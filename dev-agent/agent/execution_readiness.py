"""Offline pre-execution readiness contract.

This gate never executes Docker, modifies job state, or makes paid requests.
Production code must recheck the stop immediately before each external action,
authenticate its own caller, and use transactional admission/reservations.
"""
from dataclasses import dataclass
from .trusted_docker_executor import validate_reserved_signed_worker_plan


@dataclass(frozen=True)
class ReadinessDecision:
    job_id: str
    ready_for_supervised_review: bool
    docker_executed: bool = False


def review_execution_readiness(*, expected_job_id: str, **validation):
    if not isinstance(expected_job_id, str) or not expected_job_id:
        raise PermissionError("Expected job identity required")
    if validation.get("job_id") != expected_job_id:
        raise PermissionError("Requested job identity mismatch")
    plan = validate_reserved_signed_worker_plan(**validation)
    if plan.lifecycle.executes or plan.lifecycle.name != "swayz-test-" + expected_job_id:
        raise PermissionError("Unsafe execution plan")
    return ReadinessDecision(expected_job_id, True)


def execute_reviewed_plan(*args, **kwargs):
    raise PermissionError("Production executor not yet authorised")
