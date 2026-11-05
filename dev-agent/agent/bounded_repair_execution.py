"""One bounded repair decision after a failed trusted test run.

Never replay a signed execution job. The trusted operator must independently
admit and sign a distinct repair job and bind it to a reviewed repair proposal.
This module does not call AI, create admissions, sign, or launch Docker.
"""
import re

_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def run_one_authorised_repair(*, original_job_id, failed_result,
                              repair_job_id, approved_repair,
                              require_running, execute_repair):
    if not callable(require_running) or not callable(execute_repair):
        raise PermissionError("Trusted repair execution required")
    if (not isinstance(original_job_id, str) or not _JOB.fullmatch(original_job_id)
            or not isinstance(repair_job_id, str) or not _JOB.fullmatch(repair_job_id)
            or repair_job_id == original_job_id):
        raise PermissionError("Distinct valid repair job required")
    if (not isinstance(failed_result, dict)
            or failed_result.get("state") != "failed"
            or failed_result.get("cleanup_verified") is not True):
        raise PermissionError("Only verified clean test failures are repairable")
    if (not isinstance(approved_repair, dict)
            or set(approved_repair) != {"job_id", "proposal_sha256", "base_sha"}
            or approved_repair["job_id"] != repair_job_id
            or not isinstance(approved_repair["proposal_sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", approved_repair["proposal_sha256"])
            or not isinstance(approved_repair["base_sha"], str)
            or not re.fullmatch(r"[a-f0-9]{40}", approved_repair["base_sha"])):
        raise PermissionError("Independently approved repair identity required")
    require_running()
    # Exactly one attempt, with no automatic retries on failure or exceptions.
    outcome = execute_repair(job_id=repair_job_id, approved=approved_repair)
    if not isinstance(outcome, dict) or outcome.get("cleanup_verified") is not True:
        return {"state": "blocked", "repair_attempts": 1}
    if outcome.get("state") != "passed":
        return {"state": "blocked", "repair_attempts": 1}
    require_running()
    return {"state": "passed", "repair_attempts": 1}
