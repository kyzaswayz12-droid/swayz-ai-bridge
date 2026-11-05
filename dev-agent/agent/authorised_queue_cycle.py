"""Fail-closed one-cycle queue orchestration for Swayz development.

This is a composition boundary, not a privileged daemon. The authenticated
operator supplies an already-authorised bounded provider cycle and trusted
Docker adapter. No key access, stop release, retries, or GitHub merge here.
"""
from .offline_queue_coordinator import select_for_provider_review


def run_next_authorised_cycle(*, queue_db, job_db, control_db, task_queue,
                              require_running, authorised_cycle):
    """Select one admitted task; delegate to the existing reviewed cycle.

    The delegated cycle must atomically claim and terminally finish the task.
    Never claim early or silently retry uncertain paid or Docker outcomes.
    """
    if not callable(require_running) or not callable(authorised_cycle):
        raise PermissionError("Trusted stop and authorised cycle required")
    require_running()
    selected = select_for_provider_review(
        queue_db=queue_db, job_db=job_db, control_db=control_db)
    if selected["state"] == "empty":
        return {"state": "empty"}
    if selected["state"] != "queued_for_review":
        raise PermissionError("Unexpected queue selection")
    job_id = selected["job_id"]
    row = task_queue.get(job_id)
    if row != {"task": selected["task"], "state": "queued"}:
        raise PermissionError("Queue changed after selection")
    require_running()
    # The trusted provider-backed cycle owns authorisation, budget reservation,
    # Docker verification, atomic claim, and draft-only PR delivery.
    result = authorised_cycle(job_id=job_id)
    if result.job_id != job_id or result.state not in ("done", "blocked"):
        raise PermissionError("Invalid development cycle result")
    final = task_queue.get(job_id)
    expected = "done" if result.state == "done" else "blocked"
    if not isinstance(final, dict) or final.get("state") != expected:
        raise PermissionError("Missing durable terminal queue state")
    require_running()
    return {"job_id": job_id, "state": result.state,
            "draft_pr": result.draft_pr if result.state == "done" else None}
