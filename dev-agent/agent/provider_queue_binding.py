"""Bind the existing admitted queue to the existing provider-backed cycle.

The trusted caller must provide a bounded, independently authorised Docker
runner and draft-only GitHub adapter. No scheduler, privileged signing, stop
release, or automatic retries. An uncertain execution is never replayed.
"""
from .authorised_queue_cycle import run_next_authorised_cycle
from .provider_backed_development_cycle import run_provider_backed_cycle


def run_next_provider_cycle(*, queue_db, job_db, control_db, task_queue,
                            require_running, run_verified_tests, github,
                            cycle=run_provider_backed_cycle, **provider_options):
    if not callable(require_running) or not callable(run_verified_tests):
        raise PermissionError("Trusted stop and verified executor required")
    if getattr(github, "swayz_draft_only", False) is not True:
        raise PermissionError("Draft-only GitHub adapter required")
    if provider_options.get("owner_approved") is not True or provider_options.get("paid_calls_enabled") is not True:
        raise PermissionError("Explicit bounded provider authorisation required")
    if "operator_prepared_executor" in provider_options or "transport" in provider_options:
        raise PermissionError("Untrusted execution or transport override")
    def authorised_cycle(*, job_id):
        require_running()
        return cycle(job_id=job_id, task_queue=task_queue,
                     require_running=require_running, job_db=job_db,
                     control_db=control_db, run_verified_tests=run_verified_tests,
                     github=github, **provider_options)
    return run_next_authorised_cycle(
        queue_db=queue_db, job_db=job_db, control_db=control_db,
        task_queue=task_queue, require_running=require_running,
        authorised_cycle=authorised_cycle)
