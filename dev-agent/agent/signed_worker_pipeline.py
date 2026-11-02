"""Mock-only integration of signed handoff, journal and worker lifecycle.

This module does not grant Docker access or authenticate a real Git checkout.
It is for end-to-end state-transition tests only.
"""
from dataclasses import dataclass
import subprocess
from .signed_worker_handoff import authorise_and_plan
from .worker_runner import run_worker_plan
from .worker_journal import WorkerJournal


@dataclass(frozen=True)
class PipelineOutcome:
    state: str
    job_id: str
    docker_executed: bool = False


def simulate_signed_worker_pipeline(inbox, raw, signature, secret, *,
                                    job_id, workspace, changes, image_digest,
                                    journal_path, runner=None):
    if runner is None or runner is subprocess.run:
        raise PermissionError("Only injected mock runners are allowed")
    planned = authorise_and_plan(
        inbox, raw, signature, secret, job_id=job_id,
        workspace=workspace, changes=changes, image_digest=image_digest)
    if planned.lifecycle is None:
        return PipelineOutcome("duplicate_rejected", job_id)
    journal = WorkerJournal(journal_path)
    try:
        if not journal.record_admission(job_id):
            return PipelineOutcome("journal_duplicate_rejected", job_id)
        journal.transition(job_id, "admitted", "running")
        try:
            result = run_worker_plan(planned.lifecycle, enabled=True, runner=runner)
        except Exception:
            journal.transition(job_id, "running", "blocked",
                               excerpt="Worker invocation failed")
            raise
        if result.status == "passed":
            final = "passed"
        elif result.status == "failed":
            final = "failed"
        else:
            final = "blocked"
        journal.transition(job_id, "running", final,
                           exit_code=result.exit_code, excerpt=result.output)
        return PipelineOutcome(final, job_id)
    finally:
        journal.close()
