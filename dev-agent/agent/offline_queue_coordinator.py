"""Offline queue-to-handoff coordinator, deliberately without execution.

The coordinator never signs requests, reads credentials, invokes AI providers,
starts systemd or Docker, or writes to GitHub. A claimed task cannot be
replayed automatically after a crash; manual reconciliation is required.
"""
from .queue_selection import next_queued_job
from .atomic_queue_claim import claim_admitted_task
from .queue_handoff_readiness import inspect_handoff_readiness


def prepare_next_handoff(*, queue_db, job_db, control_db):
    selected = next_queued_job(
        queue_db=queue_db, job_db=job_db, control_db=control_db
    )
    if selected is None:
        return {"state": "empty"}
    job_id = selected["job_id"]
    if not claim_admitted_task(
        queue_db=queue_db, job_db=job_db,
        control_db=control_db, job_id=job_id
    ):
        # Another worker claimed it. Never silently pick another or retry.
        return {"state": "claim_conflict", "job_id": job_id}
    readiness = inspect_handoff_readiness(
        job_id=job_id, queue_db=queue_db,
        job_db=job_db, control_db=control_db
    )
    if readiness["state"] != "requires_operator_signed_handoff":
        raise PermissionError("Unexpected handoff state")
    return {
        "state": "requires_operator_signed_handoff",
        "job_id": job_id,
        "task": selected["task"],
    }


def select_for_provider_review(*, queue_db, job_db, control_db):
    """Select an admitted task without claiming it before AI review.

    The existing supervised cycle owns the sole atomic claim AFTER review.
    This is read-only and cannot authorise paid calls or execution.
    """
    selected = next_queued_job(
        queue_db=queue_db, job_db=job_db, control_db=control_db
    )
    if selected is None:
        return {"state": "empty"}
    return {"state": "queued_for_review", "job_id": selected["job_id"],
            "task": selected["task"]}
