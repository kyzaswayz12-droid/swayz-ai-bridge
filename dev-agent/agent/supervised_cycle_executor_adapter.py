"""Adapter from the reviewed development cycle to the existing trusted executor.

This is an explicitly supervised bridge, not a scheduler or signer.
The operator must independently prepare a root-owned signed request and
immutable snapshot. No provider calls, signing-key reads, or stop release.
"""
from .systemd_generated_job_adapter import run_prepared_generated_job


def supervised_cycle_executor(*, job_id, plan, prepared, require_running,
                              execute=run_prepared_generated_job):
    """Supply run_verified_tests to complete_supervised_cycle.

    prepared is supplied by a separately authenticated operator, never the
    model-generated plan. Fail closed on mismatched identity and missing
    independently approved snapshot metadata.
    """
    if not callable(require_running) or not callable(execute):
        raise PermissionError("Trusted execution boundary required")
    if not isinstance(prepared, dict) or set(prepared) != {
        "job_id", "snapshot", "snapshot_root", "expected_hashes",
        "signing_key_path", "approved_base_sha"
    }:
        raise PermissionError("Operator-prepared execution metadata required")
    if prepared["job_id"] != job_id or prepared["approved_base_sha"] != plan.base_sha:
        raise PermissionError("Prepared job does not match reviewed proposal")
    require_running()
    result = execute(
        job_id=job_id, snapshot=prepared["snapshot"],
        snapshot_root=prepared["snapshot_root"],
        expected_hashes=prepared["expected_hashes"],
        signing_key_path=prepared["signing_key_path"],
        require_running=require_running,
    )
    if not isinstance(result, dict) or result.get("state") != "passed" or result.get("cleanup_verified") is not True:
        return {"state": "blocked", "cleanup_verified": False}
    require_running()
    return {"state": "passed", "cleanup_verified": True}
