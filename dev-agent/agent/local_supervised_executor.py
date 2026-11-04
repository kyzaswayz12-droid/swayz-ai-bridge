"""Restricted, local supervised Docker command adapter.

No network listener or autonomy scheduler. Requires an independently validated
WorkerLifecycle and a caller-provided stop check. This is not installed on a
server, and cannot be called by the current Slack control service.
"""
import subprocess
from .worker_lifecycle import WorkerLifecycle
from .fixed_worker_policy import verify_fixed_worker_plan


def execute_local_supervised_plan(
    plan: WorkerLifecycle, *, job_id: str, image_digest: str,
    snapshot: str, approved_image_digests: frozenset,
    require_running, run_command,
):
    """Invoke a fixed worker plan only through an explicit local transport.

    Caller must separately authenticate signed provenance and reserve quota.
    The stop check must be bound to the live, authoritative control database.
    """
    if not callable(require_running) or not callable(run_command):
        raise PermissionError("Trusted stop check and transport required")
    if run_command is subprocess.run:
        raise PermissionError("Unrestricted subprocess transport forbidden")
    verify_fixed_worker_plan(
        plan, job_id=job_id, image_digest=image_digest,
        snapshot=snapshot, approved_image_digests=approved_image_digests)
    require_running()
    return run_command(plan)
