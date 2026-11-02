"""Supervised Docker executor for a separately privileged trusted service.

NOT a network endpoint, daemon or autonomous entry point. The caller must
authenticate the signed job, attest source, verify snapshot hashes, and own
the Docker privileges. Execution is disabled unless explicitly requested.
"""
from dataclasses import dataclass
from pathlib import Path
import subprocess

from .worker_lifecycle import plan_worker_lifecycle
from .fixed_worker_policy import verify_fixed_worker_plan
from .snapshot_reverification import verify_snapshot_before_execution
from .worker_journal import WorkerJournal


def _confirmed_absent(result, container_name):
    if result.returncode != 1:
        return False
    # An error code alone is insufficient: require Docker's object-not-found
    # message to refer to the exact container name.
    detail = (result.stderr or "").lower()
    return "no such object" in detail and container_name.lower() in detail


@dataclass(frozen=True)
class SupervisedResult:
    state: str
    exit_code: int | None
    cleanup_verified: bool


def execute_supervised_job(*, job_id, snapshot, snapshot_root, expected_hashes,
                           image_digest, approved_image_digests, journal_path,
                           authorised=False, executor=None):
    if authorised is not True:
        raise PermissionError("Supervised execution disabled")
    if executor is None:
        executor = subprocess.run
    root, path = Path(snapshot_root), Path(snapshot)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink() or root.resolve() != root:
        raise PermissionError("Invalid snapshot root")
    if path.parent != root or path.name != job_id:
        raise PermissionError("Snapshot outside approved root")
    if not isinstance(approved_image_digests, frozenset) or image_digest not in approved_image_digests:
        raise PermissionError("Image not approved")
    verify_snapshot_before_execution(path, expected_hashes)
    plan = plan_worker_lifecycle(job_id, image_digest, workspace=str(path))
    verify_fixed_worker_plan(plan, job_id=job_id, image_digest=image_digest,
                             snapshot=str(path), approved_image_digests=approved_image_digests)
    journal = WorkerJournal(journal_path)
    try:
        if journal.status(job_id) is None or journal.status(job_id)[0] != "admitted":
            raise PermissionError("Job must already be authenticated and admitted")
        journal.transition(job_id, "admitted", "running")
        try:
            completed = executor(list(plan.run_argv), capture_output=True, text=True,
                                 timeout=plan.timeout_seconds, check=False)
            # Docker --rm should remove a normally completed container.
            # A separate cleanup check is still mandatory before accepting success.
            inspect = executor(list(plan.inspect_argv), capture_output=True, text=True,
                               timeout=10, check=False)
            cleaned = _confirmed_absent(inspect, plan.name)
            if not cleaned:
                journal.transition(job_id, "running", "blocked",
                                   excerpt="Container cleanup unverified")
                return SupervisedResult("blocked", completed.returncode, False)
            state = "passed" if completed.returncode == 0 else "failed"
            output = ((completed.stdout or "") + "\n" + (completed.stderr or ""))[:12000]
            journal.transition(job_id, "running", state,
                               exit_code=completed.returncode, excerpt=output)
            return SupervisedResult(state, completed.returncode, True)
        except subprocess.TimeoutExpired:
            try:
                kill = executor(list(plan.kill_argv), capture_output=True, text=True,
                                timeout=10, check=False)
                inspect = executor(list(plan.inspect_argv), capture_output=True, text=True,
                                   timeout=10, check=False)
                cleaned = kill.returncode == 0 and _confirmed_absent(inspect, plan.name)
            except (OSError, subprocess.TimeoutExpired):
                cleaned = False
            journal.transition(job_id, "running", "blocked",
                               excerpt="Timeout; cleanup verified" if cleaned else "Timeout; cleanup unverified")
            return SupervisedResult("blocked", None, cleaned)
        except BaseException:
            journal.transition(job_id, "running", "blocked",
                               excerpt="Unexpected execution error; manual container inspection required")
            raise
    finally:
        journal.close()
