"""Mock-only trusted worker orchestration with durable journal transitions.

The executor is an injected test double. No Docker, paid provider or GitHub
operation is performed. This does not grant production execution authority.
"""
from dataclasses import dataclass
from .trusted_docker_executor import validate_reserved_signed_worker_plan
from .worker_journal import WorkerJournal


@dataclass(frozen=True)
class OrchestrationResult:
    job_id: str
    state: str
    docker_executed: bool = False


def simulate_journaled_execution(*, job_id: str, journal_path: str,
                                  mock_executor=None, **validation):
    if mock_executor is None or getattr(mock_executor, "swayz_test_double", False) is not True:
        raise PermissionError("Trusted test double required")
    if "job_id" in validation:
        raise PermissionError("Job identity must be supplied only once")
    # Validation must complete before any journal state transition.
    plan = validate_reserved_signed_worker_plan(job_id=job_id, **validation)
    if plan.lifecycle.executes:
        raise PermissionError("Executable plan rejected")
    journal = WorkerJournal(journal_path)
    try:
        if journal.status(job_id) != ("admitted", None, ""):
            raise PermissionError("Job not in admitted state")
        journal.transition(job_id, "admitted", "running")
        try:
            outcome = mock_executor(plan.lifecycle)
            if outcome not in ("passed", "failed", "blocked"):
                raise ValueError("Invalid executor outcome")
        except BaseException:
            journal.transition(job_id, "running", "blocked",
                               excerpt="Mock executor failed")
            raise
        journal.transition(job_id, "running", outcome)
        return OrchestrationResult(job_id, outcome)
    finally:
        journal.close()
