"""Signed-job admission linked to a non-executing worker lifecycle plan.

No Docker calls or GitHub writes. Admission is durable and duplicate IDs
cannot be replayed. Trusted source checkout remains a separate prerequisite.
"""
from dataclasses import dataclass
from .trusted_execution_controller import authorise_test_job
from .worker_lifecycle import plan_worker_lifecycle, WorkerLifecycle


@dataclass(frozen=True)
class PlannedHandoff:
    state: str
    job_id: str
    lifecycle: WorkerLifecycle | None
    docker_executed: bool = False


def authorise_and_plan(inbox, raw, signature, secret, *, job_id,
                       workspace, changes, image_digest):
    # Validate the image before durable admission; an invalid image must not burn a job ID.
    lifecycle = plan_worker_lifecycle(job_id, image_digest)
    decision = authorise_test_job(
        inbox, raw, signature, secret, job_id=job_id,
        workspace=workspace, changes=changes)
    if decision.state != "accepted_for_supervised_execution":
        return PlannedHandoff("duplicate_rejected", job_id, None)
    return PlannedHandoff("accepted_for_offline_planning", job_id, lifecycle)
