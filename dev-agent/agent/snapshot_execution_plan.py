"""Offline Docker plan for a previously verified disposable snapshot.

Does not execute Docker. Privileged worker must independently verify image,
snapshot provenance, access controls and digest before execution.
"""
from dataclasses import dataclass
from pathlib import Path
from .worker_lifecycle import plan_worker_lifecycle, WorkerLifecycle


@dataclass(frozen=True)
class SnapshotExecutionPlan:
    state: str
    lifecycle: WorkerLifecycle
    snapshot: str
    docker_executed: bool = False


def plan_snapshot_execution(*, job_id, snapshot, snapshot_root, image_digest):
    root = Path(snapshot_root)
    path = Path(snapshot)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink() or root.resolve() != root:
        raise PermissionError("Invalid snapshot root")
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise PermissionError("Invalid snapshot directory")
    if path.resolve() != path or path.parent != root or path.name != job_id:
        raise PermissionError("Snapshot outside approved root")
    if path.stat().st_mode & 0o222:
        raise PermissionError("Snapshot must not be writable")
    lifecycle = plan_worker_lifecycle(job_id, image_digest, workspace=str(path))
    mount = f"type=bind,src={path},dst=/work,readonly"
    if mount not in lifecycle.run_argv:
        raise PermissionError("Snapshot mount missing")
    return SnapshotExecutionPlan("awaiting_trusted_worker", lifecycle, str(path))
