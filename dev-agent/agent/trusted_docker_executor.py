"""Fail-closed validation boundary for a future privileged Docker executor.

This module performs NO execution, database writes, or network requests.
It must not be used as an authorisation to start a container.
"""
from dataclasses import dataclass
from pathlib import Path

from .worker_lifecycle import WorkerLifecycle, plan_worker_lifecycle
from .fixed_worker_policy import verify_fixed_worker_plan
from .snapshot_reverification import verify_snapshot_before_execution


@dataclass(frozen=True)
class ValidatedWorkerPlan:
    """A verified plan, not an execution capability or permission token."""
    lifecycle: WorkerLifecycle
    snapshot: str
    image_digest: str


def validate_trusted_worker_plan(
    *,
    job_id: str,
    snapshot: str,
    snapshot_root: str,
    expected_hashes: dict,
    image_digest: str,
    approved_image_digests: frozenset,
    timeout_seconds: int = 120,
) -> ValidatedWorkerPlan:
    """Rebuild a fixed plan independently; reject modified or unsafe inputs.

    The privileged service must additionally authenticate the signed job,
    check the persistent emergency stop, admission journal and budget, and
    recheck all inputs immediately before execution.
    """
    if not isinstance(approved_image_digests, frozenset):
        raise PermissionError("Immutable approved image set required")
    if image_digest not in approved_image_digests:
        raise PermissionError("Image digest not approved")
    root = Path(snapshot_root)
    path = Path(snapshot)
    if (not root.is_absolute() or not root.is_dir()
            or root.is_symlink() or root.resolve() != root):
        raise PermissionError("Invalid snapshot root")
    if (not path.is_absolute() or not path.is_dir()
            or path.is_symlink() or path.resolve() != path
            or path.parent != root or path.name != job_id):
        raise PermissionError("Invalid snapshot path")
    if path.stat().st_mode & 0o222:
        raise PermissionError("Snapshot is writable")
    verify_snapshot_before_execution(str(path), expected_hashes)
    plan = plan_worker_lifecycle(
        job_id, image_digest, timeout_seconds=timeout_seconds,
        workspace=str(path),
    )
    verify_fixed_worker_plan(
        plan, job_id=job_id, image_digest=image_digest,
        snapshot=str(path), approved_image_digests=approved_image_digests,
    )
    if plan.executes:
        raise PermissionError("Executable plan forbidden at validation boundary")
    return ValidatedWorkerPlan(plan, str(path), image_digest)


def execute_trusted_worker(*args, **kwargs):
    """Explicitly refuse execution until a separate privileged service exists."""
    raise PermissionError("Production Docker execution is not enabled")
