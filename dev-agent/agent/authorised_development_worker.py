"""Compose unattended polling with the existing bounded provider queue cycle.

The trusted deployment must inject independently authenticated fixed
credentials, repair admission/signing and Docker/GitHub adapters. This module
does not enable those authorities, and is not a standalone systemd service.
"""
from .unattended_worker_loop import run_worker_loop
from .bounded_provider_queue_cycle import run_one_bounded_provider_queue_cycle

def run_authorised_development_worker(*, require_running, shutdown_requested,
                                      run_primary, prepare_repair, run_repair,
                                      queue_options, sleep=None, max_cycles=20):
    if not isinstance(queue_options, dict):
        raise PermissionError("Trusted queue configuration required")
    if any(k in queue_options for k in (
            "require_running", "run_primary", "prepare_repair", "run_repair")):
        raise PermissionError("Conflicting trusted execution authorities")
    if queue_options.get("owner_approved") is not True or queue_options.get("paid_calls_enabled") is not True:
        raise PermissionError("Paid unattended execution not independently authorised")
    def one_cycle():
        return run_one_bounded_provider_queue_cycle(
            require_running=require_running, run_primary=run_primary,
            prepare_repair=prepare_repair, run_repair=run_repair,
            **queue_options)
    args=dict(require_running=require_running,
              shutdown_requested=shutdown_requested,
              run_one_cycle=one_cycle,max_cycles=max_cycles)
    if sleep is not None:
        args["sleep"]=sleep
    return run_worker_loop(**args)
