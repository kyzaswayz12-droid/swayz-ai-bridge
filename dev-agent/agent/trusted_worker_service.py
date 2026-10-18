"""Mock-only service boundary for a prepared, journaled worker job.

No real Docker execution is allowed here. A privileged service must
independently authenticate provenance and recheck snapshot integrity.
"""
import subprocess
from .worker_journal import WorkerJournal
from .worker_runner import run_worker_plan
from .snapshot_execution_plan import plan_snapshot_execution
from .snapshot_reverification import verify_snapshot_before_execution


def simulate_worker_service(*, job_id, snapshot, snapshot_root, expected_hashes,
                            image_digest, journal_path, runner=None):
    if runner is None or runner is subprocess.run:
        raise PermissionError("Real Docker runner forbidden")
    journal = WorkerJournal(journal_path)
    try:
        if journal.status(job_id) is None or journal.status(job_id)[0] != "admitted":
            raise PermissionError("Job not admitted")
        try:
            verify_snapshot_before_execution(snapshot, expected_hashes)
            plan = plan_snapshot_execution(
                job_id=job_id, snapshot=snapshot, snapshot_root=snapshot_root,
                image_digest=image_digest)
        except Exception:
            journal.transition(job_id, "admitted", "blocked",
                               excerpt="Snapshot or image planning rejected")
            raise
        journal.transition(job_id, "admitted", "running")
        try:
            result = run_worker_plan(plan.lifecycle, enabled=True, runner=runner)
        except Exception:
            journal.transition(job_id, "running", "blocked",
                               excerpt="Worker invocation error")
            raise
        state = "passed" if result.status == "passed" else (
            "failed" if result.status == "failed" else "blocked")
        journal.transition(job_id, "running", state,
                           exit_code=result.exit_code, excerpt=result.output)
        return state
    finally:
        journal.close()
