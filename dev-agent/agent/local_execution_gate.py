"""Local-only supervised execution gate; production execution remains disabled.

This is the integration seam for a future independently authorised worker
service. No Docker invocation, API call, or persistent state mutation occurs.
"""
from dataclasses import dataclass
from .trusted_docker_executor import validate_reserved_signed_worker_plan
from .worker_recovery_review import review_worker_recovery


@dataclass(frozen=True)
class LocalExecutionReview:
    job_id: str
    state: str
    requires_owner_approval: bool = True
    docker_executed: bool = False


def review_local_execution(*, job_id, **validation):
    """Validate the full signed, admitted, budgeted plan without executing."""
    if "job_id" in validation:
        raise PermissionError("Job ID must be bound exactly once")
    plan = validate_reserved_signed_worker_plan(job_id=job_id, **validation)
    if plan.lifecycle.executes or plan.lifecycle.name != "swayz-test-" + job_id:
        raise PermissionError("Unsafe lifecycle plan")
    return LocalExecutionReview(job_id, "awaiting_supervised_execution")


def activate_local_execution(*args, **kwargs):
    """Never enable a privileged executor through a Python boolean or flag."""
    raise PermissionError("Local privileged execution service not installed")
