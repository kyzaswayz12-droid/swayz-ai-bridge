"""Offline final dispatch revalidation.

This is not a production executor. It rechecks the signed, admitted,
budgeted job and immutable snapshot immediately before a test-only handoff.
No Docker calls or persistent state changes.
"""
from dataclasses import dataclass
from .trusted_docker_executor import validate_reserved_signed_worker_plan


@dataclass(frozen=True)
class FinalDispatchDecision:
    job_id: str
    ready_for_supervised_handoff: bool
    docker_executed: bool = False


def revalidate_before_handoff(*, job_id: str, **validation):
    if "job_id" in validation:
        raise PermissionError("Job identity supplied twice")
    plan = validate_reserved_signed_worker_plan(job_id=job_id, **validation)
    if plan.lifecycle.executes or plan.lifecycle.name != "swayz-test-" + job_id:
        raise PermissionError("Untrusted worker plan")
    return FinalDispatchDecision(job_id, True)
