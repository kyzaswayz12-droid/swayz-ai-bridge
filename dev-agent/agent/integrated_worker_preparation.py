"""Offline signed snapshot -> reverify -> Docker plan -> durable journal.

No Docker execution. A privileged worker must separately attest the source
commit and protect snapshots against modification before actual execution.
"""
from dataclasses import dataclass
from pathlib import Path
from .signed_worker_snapshot import stage_signed_worker_snapshot
from .staging_manifest import verify_staged_changes
from .snapshot_reverification import verify_snapshot_before_execution
from .snapshot_execution_plan import plan_snapshot_execution
from .worker_journal import WorkerJournal


@dataclass(frozen=True)
class PreparedJob:
    state: str
    job_id: str
    snapshot: str | None
    docker_argv: tuple[str, ...] | None
    docker_executed: bool = False


def prepare_integrated_job(inbox, raw, signature, secret, *,
                           job_id, workspace, changes, image_digest,
                           snapshot_root, journal_path):
    root = Path(snapshot_root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir() or root.resolve() != root:
        raise PermissionError("Invalid snapshot root")
    hashes = {name: entry["sha256"] for name, entry in
              verify_staged_changes(workspace, changes).items()}
    staged = stage_signed_worker_snapshot(
        inbox, raw, signature, secret, job_id=job_id, workspace=workspace,
        changes=changes, image_digest=image_digest,
        snapshot_directory=root / job_id)
    if staged.snapshot is None:
        return PreparedJob("duplicate_rejected", job_id, None, None)
    journal = WorkerJournal(journal_path)
    try:
        if not journal.record_admission(job_id):
            raise PermissionError("Duplicate journal admission")
        try:
            verify_snapshot_before_execution(staged.snapshot, hashes)
            plan = plan_snapshot_execution(
                job_id=job_id, snapshot=staged.snapshot,
                snapshot_root=str(root), image_digest=image_digest)
        except Exception:
            journal.transition(job_id, "admitted", "blocked",
                               excerpt="Snapshot verification or planning failed")
            raise
        return PreparedJob("awaiting_trusted_worker", job_id,
                           staged.snapshot, plan.lifecycle.run_argv)
    finally:
        journal.close()
