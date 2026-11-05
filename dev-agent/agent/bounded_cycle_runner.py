"""Fail-closed bounded development cycle including one separately authorised repair.

This is an integration callback for the existing supervised coordinator, not
an autonomous signer or model transport. Repair preparation and model review
must be independently authorised by the trusted caller. No retries.
"""
from .bounded_repair_execution import run_one_authorised_repair


def bounded_test_runner(*, job_id, plan, run_primary, prepare_repair,
                        run_repair, require_running):
    if not all(callable(x) for x in
               (run_primary, prepare_repair, run_repair, require_running)):
        raise PermissionError("Trusted bounded execution dependencies required")
    require_running()
    primary = run_primary(job_id=job_id, plan=plan)
    if not isinstance(primary, dict):
        raise PermissionError("Invalid executor result")
    if primary.get("state") == "passed" and primary.get("cleanup_verified") is True:
        require_running()
        return primary
    if primary.get("state") != "failed" or primary.get("cleanup_verified") is not True:
        return {"state":"blocked","cleanup_verified":False}
    require_running()
    # Trusted preparation independently admits and signs a distinct job.
    # The model-generated plan cannot choose the repair execution identity.
    prepared = prepare_repair(original_job_id=job_id, plan=plan,
                              failed_result=primary)
    if not isinstance(prepared, dict) or set(prepared) != {
        "repair_job_id", "approved_repair"
    }:
        raise PermissionError("Trusted repair preparation required")
    outcome = run_one_authorised_repair(
        original_job_id=job_id, failed_result=primary,
        repair_job_id=prepared["repair_job_id"],
        approved_repair=prepared["approved_repair"],
        require_running=require_running,
        execute_repair=run_repair)
    if outcome["state"] != "passed":
        return {"state":"blocked","cleanup_verified":False}
    require_running()
    return {"state":"passed","cleanup_verified":True}
