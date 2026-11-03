"""Supervised Docker lifecycle adapter.

This adapter has no default executor and is not wired to an API, service,
or autonomous dispatcher. The caller must independently authenticate the job,
verify the snapshot and approved image, check admission and spending, and
enforce the stop at dispatch. Do not expose it as a remote execution endpoint.
"""
from dataclasses import dataclass
import subprocess
from .worker_lifecycle import WorkerLifecycle
from .cleanup_evidence import cleanup_evidence_verified


@dataclass(frozen=True)
class SupervisedResult:
    state: str
    exit_code: int | None
    cleanup_verified: bool
    output: str


def run_supervised_lifecycle(plan: WorkerLifecycle, *, transport=None,
                             daemon_probe=None) -> SupervisedResult:
    """Use explicitly supplied trusted transports; no implicit Docker access.

    The transport must implement subprocess.run-compatible arguments. A
    separate probe must confirm daemon health after cleanup. Fail closed.
    """
    if transport is None or daemon_probe is None:
        raise PermissionError("Supervised transport and daemon probe required")
    if transport is subprocess.run or not callable(transport) or not callable(daemon_probe):
        raise PermissionError("Direct subprocess execution forbidden")
    if not isinstance(plan, WorkerLifecycle) or plan.executes:
        raise PermissionError("Invalid supervised plan")
    if plan.run_argv[:2] != ("docker", "run") or "--rm" not in plan.run_argv:
        raise PermissionError("Unexpected Docker invocation")
    if plan.kill_argv != ("docker", "kill", plan.name):
        raise PermissionError("Unexpected kill plan")
    if plan.inspect_argv != ("docker", "inspect", plan.name):
        raise PermissionError("Unexpected inspect plan")

    result = None
    timed_out = False
    try:
        result = transport(list(plan.run_argv), capture_output=True, text=True,
                           timeout=plan.timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        timed_out = True
    except (OSError, subprocess.SubprocessError):
        pass

    # Even a successful run must have its cleanup independently checked.
    try:
        transport(list(plan.kill_argv), capture_output=True, text=True,
                  timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        inspect = transport(list(plan.inspect_argv), capture_output=True,
                            text=True, timeout=10, check=False)
        healthy = daemon_probe()
        cleaned = cleanup_evidence_verified(
            container_name=plan.name, inspect_exit_code=inspect.returncode,
            inspect_stderr=inspect.stderr or "", daemon_healthy=healthy)
    except (OSError, subprocess.SubprocessError, ValueError):
        cleaned = False
    if not cleaned:
        return SupervisedResult("cleanup_unverified", None, False, "")
    if timed_out:
        return SupervisedResult("timed_out", None, True, "")
    if result is None or type(result.returncode) is not int:
        return SupervisedResult("blocked", None, True, "")
    output = ((result.stdout or "") + (result.stderr or ""))[:12000]
    return SupervisedResult(
        "passed" if result.returncode == 0 else "failed",
        result.returncode, True, output)
