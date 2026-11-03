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
from .fixed_docker_transport import FixedDockerTransport
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
    if (getattr(transport_factory, "swayz_test_double", False) is not True
            or getattr(lifecycle_runner, "swayz_test_double", False) is not True):
        raise PermissionError("Only test-only service dependencies permitted")
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


def run_operator_supervised_worker(
    *, job_id: str, journal_path: str, server_control_db: str,
    **validation,
) -> SupervisedWorkerOutcome:
    """Explicit local operator path; no listener, scheduler, or API endpoint.

    Caller is a trusted privileged operator entrypoint, never a model-generated
    request. It must authenticate the operator, pin paths and load signing
    credentials from protected server configuration. The production stop must
    be read from the authoritative control database.
    """
    from .persistent_stop_guard import PersistentStopGuard
    from .fixed_docker_transport import FixedDockerTransport
    from .supervised_lifecycle_adapter import run_supervised_lifecycle
    if "job_id" in validation or "control_db" in validation or "journal_db" in validation:
        raise PermissionError("Server-owned identities and state paths")
    if not isinstance(job_id, str) or not job_id:
        raise PermissionError("Job ID required")
    # Reject an engaged or missing stop before expensive verification.
    guard = PersistentStopGuard(server_control_db)
    guard.require_running()
    plan = validate_reserved_signed_worker_plan(
        job_id=job_id, control_db=server_control_db,
        journal_db=journal_path, **validation)
    if plan.lifecycle.executes or plan.lifecycle.name != "swayz-test-" + job_id:
        raise PermissionError("Invalid worker lifecycle")
    # This constructor re-derives the fixed Docker command and rejects
    # unmounted, writable, or unexpected command plans.
    transport = FixedDockerTransport(plan.lifecycle, require_running=guard.require_running)
    journal = WorkerJournal(journal_path)
    try:
        if journal.status(job_id) != ("admitted", None, ""):
            raise PermissionError("Job not admitted or already claimed")
        # Atomic state transition prevents two operators from claiming one job.
        journal.transition(job_id, "admitted", "running")
        try:
            result = run_supervised_lifecycle(
                plan.lifecycle, transport=transport,
                daemon_probe=transport.daemon_healthy)
        except BaseException:
            journal.transition(job_id, "running", "blocked",
                               excerpt="Supervised execution interrupted")
            raise
        state = ("passed" if result.cleanup_verified and result.state == "passed"
                 else "failed" if result.cleanup_verified and result.state == "failed"
                 else "blocked")
        journal.transition(job_id, "running", state,
                           exit_code=result.exit_code,
                           excerpt=(result.output or "")[:12000])
        return SupervisedWorkerOutcome(
            job_id, state, result.cleanup_verified, True)
    finally:
        journal.close()
