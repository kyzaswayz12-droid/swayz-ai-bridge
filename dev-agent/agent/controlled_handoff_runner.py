"""One-shot controlled admission-to-executor orchestration.

Only an authenticated operator can supply these trusted callbacks. This is
NOT an unattended service. Never release stop, sign directly, retry, or
fabricate a journal success. A failed or uncertain job remains blocked.
"""
import re

_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def run_controlled_handoff(*, job_id, require_running, verify_authority,
                           prepare_authorised_job, sign_prepared_job,
                           run_trusted_executor, journal_status):
    if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise PermissionError("Invalid job identity")
    callbacks = (require_running, verify_authority, prepare_authorised_job,
                 sign_prepared_job, run_trusted_executor, journal_status)
    if not all(callable(x) for x in callbacks):
        raise PermissionError("Independent runtime authorities required")
    require_running()
    if verify_authority(job_id=job_id) is not True:
        raise PermissionError("Explicit supervised operator authority required")
    require_running()
    # Preparation owns the atomic queue claim, daily quota, journal admission,
    # protected snapshot, hashes and approved image verification.
    prepared = prepare_authorised_job(job_id=job_id)
    if not isinstance(prepared, dict) or prepared != {
            "state": "admitted", "job_id": job_id}:
        raise PermissionError("Independent admission not confirmed")
    require_running()
    signed = sign_prepared_job(job_id=job_id)
    if not isinstance(signed, dict) or signed != {
            "state": "admitted", "job_id": job_id}:
        raise PermissionError("Protected signer did not confirm job")
    require_running()
    result = run_trusted_executor(job_id=job_id)
    # No replay if execution returns an uncertain result.
    record = journal_status(job_id=job_id)
    if (not isinstance(result, dict) or result.get("state") != "passed"
            or result.get("cleanup_verified") is not True
            or not isinstance(record, tuple) or len(record) < 1
            or record[0] != "passed"):
        return {"state": "blocked", "job_id": job_id,
                "cleanup_verified": False}
    require_running()
    return {"state": "passed", "job_id": job_id,
            "cleanup_verified": True}
