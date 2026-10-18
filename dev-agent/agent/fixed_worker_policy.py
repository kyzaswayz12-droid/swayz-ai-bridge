"""Validate a Docker execution plan against an independently rebuilt policy.

This is an offline validation component; it never runs Docker.
"""
from .worker_lifecycle import WorkerLifecycle, plan_worker_lifecycle


def verify_fixed_worker_plan(plan, *, job_id, image_digest, snapshot,
                             approved_image_digests):
    if not isinstance(approved_image_digests, frozenset) or image_digest not in approved_image_digests:
        raise PermissionError("Unapproved worker image")
    if not isinstance(plan, WorkerLifecycle):
        raise PermissionError("Invalid worker plan")
    expected = plan_worker_lifecycle(job_id, image_digest, workspace=snapshot,
                                     timeout_seconds=plan.timeout_seconds)
    if plan != expected:
        raise PermissionError("Docker plan differs from fixed policy")
    return True
