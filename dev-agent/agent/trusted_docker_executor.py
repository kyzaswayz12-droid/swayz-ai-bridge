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


def validate_admitted_worker_plan(*, control_db: str, journal_db: str, **plan_args):
    """Offline gate for a previously admitted job; never executes Docker.

    Both databases must exist. Read-only queries cannot create or enable
    anything. This check is NOT sufficient for production authorisation:
    the future service must independently verify signed provenance, budget
    reservations and recheck the stop immediately before execution.
    """
    import sqlite3

    def read_one(path, statement, parameters=()):
        p = Path(path)
        if not p.is_absolute() or p.is_symlink() or not p.is_file():
            raise PermissionError("Required state database missing or unsafe")
        try:
            with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
                return db.execute(statement, parameters).fetchone()
        except sqlite3.Error as exc:
            raise PermissionError("Required state database unreadable") from exc

    stop = read_one(control_db, "SELECT stopped FROM agent_control WHERE id=1")
    if stop != (0,):
        raise PermissionError("Emergency stop engaged or invalid")
    job_id = plan_args.get("job_id")
    if not isinstance(job_id, str):
        raise PermissionError("Job ID required")
    admitted = read_one(journal_db, "SELECT state FROM worker_jobs WHERE job_id=?", (job_id,))
    if admitted != ("admitted",):
        raise PermissionError("Job is not admitted")
    return validate_trusted_worker_plan(**plan_args)


def validate_signed_admitted_worker_plan(
    *, raw: bytes, signature: str, secret: bytes,
    expected_manifest: str, expected_repository: str,
    expected_commit_sha: str, **plan_args,
):
    """Verify signed job identity before read-only admission and plan checks.

    No execution capability is granted. The future privileged service must
    separately verify immutable checkout provenance, durable replay rejection,
    quota/budget reservation and stop state at the execution boundary.
    """
    from .signed_handoff import verify_manifest_job

    job = verify_manifest_job(raw, signature, secret, expected_manifest)
    if (job.job_id != plan_args.get("job_id")
            or job.repository != expected_repository
            or job.commit_sha != expected_commit_sha):
        raise PermissionError("Signed job identity mismatch")
    return validate_admitted_worker_plan(**plan_args)
