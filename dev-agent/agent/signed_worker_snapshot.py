"""Offline signed-job snapshot staging.

Verifies signed handoff and staged file hashes before making a disposable
snapshot. No Docker calls or source checkout; race-free privileged staging
must be implemented separately before production use.
"""
from dataclasses import dataclass
from pathlib import Path
from .signed_worker_handoff import authorise_and_plan
from .staging_manifest import verify_staged_changes
from .worker_snapshot import prepare_readonly_snapshot


@dataclass(frozen=True)
class StagedWorkerJob:
    state: str
    job_id: str
    snapshot: str | None
    docker_executed: bool = False


def stage_signed_worker_snapshot(inbox, raw, signature, secret, *,
                                 job_id, workspace, changes, image_digest,
                                 snapshot_directory):
    source = Path(workspace)
    target = Path(snapshot_directory)
    if not target.is_absolute() or target.name != job_id:
        raise ValueError("Snapshot must be named for job")
    if target.exists():
        raise PermissionError("Snapshot already exists")
    # Verify file set and content prior to signed admission.
    manifest = verify_staged_changes(source, changes)
    decision = authorise_and_plan(
        inbox, raw, signature, secret, job_id=job_id,
        workspace=source, changes=changes, image_digest=image_digest)
    if decision.lifecycle is None:
        return StagedWorkerJob("duplicate_rejected", job_id, None)
    hashes = {name: details["sha256"] for name, details in manifest.items()}
    snapshot = prepare_readonly_snapshot(source, target, expected_files=hashes)
    return StagedWorkerJob("snapshot_prepared", job_id, str(snapshot))
