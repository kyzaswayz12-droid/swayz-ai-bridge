"""Mockable trusted-worker lifecycle runner, disabled by default.

Not a production sandbox: a separate privileged worker must verify signed
job provenance, immutable checkout, mounts and image approval first.
"""
from dataclasses import dataclass
import subprocess
from .worker_lifecycle import WorkerLifecycle


@dataclass(frozen=True)
class WorkerRunResult:
    status: str
    exit_code: int | None
    output: str
    cleanup_attempted: bool
    cleanup_verified: bool


def run_worker_plan(plan: WorkerLifecycle, *, enabled=False,
                    runner=subprocess.run) -> WorkerRunResult:
    if not enabled:
        raise PermissionError("Trusted worker execution disabled")
    if not isinstance(plan, WorkerLifecycle) or plan.executes:
        raise ValueError("Invalid worker plan")
    # Explicitly refuse real subprocess.run. Only injected test runners
    # are permitted in this staging implementation.
    if runner is subprocess.run:
        raise PermissionError("Real Docker execution not enabled")
    try:
        result = runner(list(plan.run_argv), capture_output=True, text=True,
                        timeout=plan.timeout_seconds, check=False)
        return WorkerRunResult("passed" if result.returncode == 0 else "failed",
                               result.returncode,
                               ((result.stdout or "") + (result.stderr or ""))[:12000],
                               False, False)
    except subprocess.TimeoutExpired:
        try:
            killed = runner(list(plan.kill_argv), capture_output=True, text=True,
                            timeout=10, check=False)
            inspection = runner(list(plan.inspect_argv), capture_output=True,
                                text=True, timeout=10, check=False)
            cleaned = killed.returncode == 0 and inspection.returncode != 0
        except (OSError, subprocess.TimeoutExpired):
            cleaned = False
        return WorkerRunResult("timed_out" if cleaned else "cleanup_unverified",
                               None, "Worker deadline exceeded", True, cleaned)
