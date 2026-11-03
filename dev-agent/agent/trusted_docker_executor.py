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


def validate_reserved_signed_worker_plan(
    *, job_db: str, budget_db: str, request_id: str, provider: str,
    now, **signed_plan_args,
):
    """Check durable daily admission and a reserved request, without writing.

    A reservation check is not a payment guarantee, and this function never
    authorises execution. The future dispatcher must use transactional
    reservation APIs and recheck the stop at the actual execution boundary.
    """
    import sqlite3
    from datetime import datetime, timezone
    from decimal import Decimal, InvalidOperation

    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise PermissionError("Timezone-aware clock required")
    if provider not in ("openai", "anthropic"):
        raise PermissionError("Provider not approved")
    if not isinstance(request_id, str) or not request_id:
        raise PermissionError("Request ID required")

    def query(path, statement, params):
        p = Path(path)
        if not p.is_absolute() or p.is_symlink() or not p.is_file():
            raise PermissionError("Required ledger missing or unsafe")
        try:
            with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
                return db.execute(statement, params).fetchall()
        except sqlite3.Error as exc:
            raise PermissionError("Required ledger unreadable") from exc

    day = now.astimezone(timezone.utc).date().isoformat()
    job_id = signed_plan_args.get("job_id")
    admitted = query(job_db,
        "SELECT day_utc FROM admitted_jobs WHERE job_id=?", (job_id,))
    if admitted != [(day,)]:
        raise PermissionError("Daily job admission missing or expired")
    count = query(job_db,
        "SELECT COUNT(*) FROM admitted_jobs WHERE day_utc=?", (day,))
    if len(count) != 1 or not 1 <= count[0][0] <= 20:
        raise PermissionError("Daily job quota invalid")
    reservation = query(budget_db,
        "SELECT provider,day_utc,reserved_gbp,status,actual_gbp FROM gbp_reservations WHERE request_id=?",
        (request_id,))
    if len(reservation) != 1 or reservation[0][0:2] != (provider, day):
        raise PermissionError("API reservation missing or expired")
    if reservation[0][3] != "reserved" or reservation[0][4] is not None:
        raise PermissionError("API reservation not pending")
    rows = query(budget_db,
        "SELECT reserved_gbp,actual_gbp FROM gbp_reservations WHERE day_utc=?", (day,))
    try:
        used = sum((Decimal(actual if actual is not None else held)
                    for held, actual in rows), Decimal("0"))
        if not used.is_finite() or used < 0 or used > Decimal("5.00"):
            raise PermissionError("GBP budget limit exceeded or invalid")
        reserved = Decimal(reservation[0][2])
        if not reserved.is_finite() or reserved <= 0 or reserved > Decimal("5.00"):
            raise PermissionError("Invalid API reservation amount")
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PermissionError("Malformed budget ledger") from exc
    return validate_signed_admitted_worker_plan(**signed_plan_args)
