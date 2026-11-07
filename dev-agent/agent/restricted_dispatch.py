"""Restricted, operator-controlled dispatch of a prepared offline test job.

No scheduler, signing, paid API calls, stop release, or direct Docker access.
A separate trusted service must authenticate the caller and prepare the
root-owned signed request. This module invokes only the fixed systemd adapter.
"""
import os
import re
from pathlib import Path
from .persistent_stop_guard import PersistentStopGuard
from .systemd_generated_job_adapter import run_prepared_generated_job

_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def dispatch_prepared_offline_job(*, job_id, snapshot, snapshot_root,
                                  expected_hashes, signing_key_path, stop_db,
                                  execute=run_prepared_generated_job):
    if os.geteuid() != 0:
        raise PermissionError("Privileged operator required")
    if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise ValueError("Invalid job ID")
    if execute is not run_prepared_generated_job:
        # A test double is permitted only when explicitly marked for tests.
        if getattr(execute, "swayz_test_double", False) is not True:
            raise PermissionError("Executor substitution forbidden")
    guard = PersistentStopGuard(stop_db)
    guard.require_running()
    root = Path(snapshot_root)
    snap = Path(snapshot)
    if not root.is_absolute() or root.is_symlink() or snap != root / job_id:
        raise PermissionError("Invalid snapshot identity")
    result = execute(job_id=job_id, snapshot=str(snap),
                     snapshot_root=str(root), expected_hashes=expected_hashes,
                     signing_key_path=signing_key_path,
                     require_running=guard.require_running)
    if not isinstance(result, dict) or result.get("state") != "passed" or result.get("cleanup_verified") is not True:
        return {"state": "blocked", "cleanup_verified": False}
    guard.require_running()
    return {"state": "passed", "cleanup_verified": True}
