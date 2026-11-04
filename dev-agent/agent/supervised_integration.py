"""Offline integration between validated job admission and supervised lifecycle.

This module never invokes the Docker daemon itself. It accepts an explicitly
injected test transport only and is not connected to the production worker.
"""
from dataclasses import dataclass
from .trusted_docker_executor import validate_reserved_signed_worker_plan
from .supervised_lifecycle_adapter import run_supervised_lifecycle


@dataclass(frozen=True)
class SupervisedIntegrationDecision:
    job_id: str
    state: str
    cleanup_verified: bool
    production_enabled: bool = False


def simulate_supervised_integration(*, job_id, test_transport=None,
                                    test_daemon_probe=None, **validation):
    if "job_id" in validation:
        raise PermissionError("Job identity must be supplied once")
    if (test_transport is None
            or getattr(test_transport, "swayz_test_double", False) is not True
            or test_daemon_probe is None
            or getattr(test_daemon_probe, "swayz_test_double", False) is not True):
        raise PermissionError("Explicit test-only transport and probe required")
    plan = validate_reserved_signed_worker_plan(job_id=job_id, **validation)
    if plan.lifecycle.executes:
        raise PermissionError("Executable plan forbidden")
    result = run_supervised_lifecycle(
        plan.lifecycle, transport=test_transport, daemon_probe=test_daemon_probe)
    return SupervisedIntegrationDecision(job_id, result.state,
                                         result.cleanup_verified)
