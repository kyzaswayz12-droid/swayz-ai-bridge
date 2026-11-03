"""Local supervised worker service orchestration.

NOT deployed or exposed as an API. A privileged deployment must independently
authenticate its local caller, protect the signing key, ensure the configured
SQLite ledgers are authoritative, and establish race-resistant workspace
isolation. This module does not enable unattended execution.
"""
from dataclasses import dataclass
from .trusted_docker_executor import validate_reserved_signed_worker_plan
from .worker_journal import WorkerJournal
from .guarded_transport_factory import build_guarded_transport
from .supervised_lifecycle_adapter import run_supervised_lifecycle


@dataclass(frozen=True)
class SupervisedWorkerOutcome:
    job_id: str
    state: str
    cleanup_verified: bool
    docker_executed: bool


def run_local_supervised_worker(
    *, job_id: str, journal_path: str, server_control_db: str,
    transport_factory=build_guarded_transport,
    lifecycle_runner=run_supervised_lifecycle,
    **validation,
) -> SupervisedWorkerOutcome:
    """Validate, claim a journaled job, run and record a supervised outcome.

    This function has no remote endpoint or scheduler. Its injectable
    dependencies are for isolated testing; production deployment must pin
    them in a separately reviewed, privileged entrypoint.
    """
    if "job_id" in validation or "control_db" in validation:
        raise PermissionError("Job identity and control path are server-selected")
    if not isinstance(job_id, str) or not job_id:
        raise PermissionError("Job ID required")
    plan = validate_reserved_signed_worker_plan(
        job_id=job_id, control_db=server_control_db,
        journal_db=journal_path, **validation)
    if plan.lifecycle.executes or plan.lifecycle.name != "swayz-test-" + job_id:
        raise PermissionError("Invalid fixed worker plan")

    # Recheck the stop as part of constructing the guarded transport.
    transport = transport_factory(plan.lifecycle, server_control_db=server_control_db)
    journal = WorkerJournal(journal_path)
    try:
        if journal.status(job_id) != ("admitted", None, ""):
            raise PermissionError("Job not admitted or already used")
        journal.transition(job_id, "admitted", "running")
        try:
            result = lifecycle_runner(
                plan.lifecycle, transport=transport,
                daemon_probe=transport.daemon_healthy)
        except BaseException:
            journal.transition(job_id, "running", "blocked",
                               excerpt="Supervised worker invocation failed")
            raise
        if not result.cleanup_verified:
            state = "blocked"
        elif result.state == "passed":
            state = "passed"
        elif result.state == "failed":
            state = "failed"
        else:
            state = "blocked"
        journal.transition(job_id, "running", state,
                           exit_code=result.exit_code,
                           excerpt=(result.output or "")[:12000])
        return SupervisedWorkerOutcome(
            job_id, state, result.cleanup_verified,
            bool(getattr(result, "docker_executed", False)))
    finally:
        journal.close()
