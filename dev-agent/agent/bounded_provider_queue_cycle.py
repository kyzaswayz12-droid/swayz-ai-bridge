"""Compose the already-authorised queue, AI cycle and bounded test callback.

This is a synchronous trusted-call boundary, NOT a background service.
The trusted caller must supply independent repair preparation and executor
functions. No signing key, Docker socket, model credentials or stop release
are handled here.
"""
from .provider_queue_binding import run_next_provider_cycle
from .bounded_cycle_runner import bounded_test_runner


def run_one_bounded_provider_queue_cycle(
        *, run_primary, prepare_repair, run_repair, require_running, **options):
    if not all(callable(x) for x in
               (run_primary, prepare_repair, run_repair, require_running)):
        raise PermissionError("Trusted executor and repair authority required")

    def verified_tests(*, job_id, plan):
        return bounded_test_runner(
            job_id=job_id, plan=plan, run_primary=run_primary,
            prepare_repair=prepare_repair, run_repair=run_repair,
            require_running=require_running)

    return run_next_provider_cycle(
        require_running=require_running, run_verified_tests=verified_tests,
        **options)
