"""Offline trusted execution orchestration contract.

This module never calls Docker or providers. It models the critical
authorisation ordering and deliberately rejects a real execution backend.
"""
from dataclasses import dataclass
from .trusted_docker_executor import validate_reserved_signed_worker_plan


@dataclass(frozen=True)
class OfflineExecutionDecision:
    job_id: str
    state: str
    docker_executed: bool = False


def simulate_trusted_execution(*, mock_executor=None, **validation_args):
    """Validate every gate before invoking an explicitly injected test double.

    This is NOT a production execution entrypoint. The mock is intentionally
    limited to an object with an explicit test-only marker, so accidentally
    passing subprocess.run or an arbitrary callable is rejected.
    """
    if mock_executor is None or getattr(mock_executor, "swayz_test_double", False) is not True:
        raise PermissionError("Only an explicit test executor is permitted")
    plan = validate_reserved_signed_worker_plan(**validation_args)
    job_id = validation_args.get("job_id")
    if plan.lifecycle.executes:
        raise PermissionError("Executable plan not allowed")
    result = mock_executor(plan.lifecycle)
    if result not in ("passed", "failed", "blocked"):
        raise PermissionError("Invalid mock execution result")
    return OfflineExecutionDecision(job_id=job_id, state=result)
