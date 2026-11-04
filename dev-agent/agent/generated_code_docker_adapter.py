"""Prepare reviewed generated code for the existing trusted Docker executor.

This adapter never invokes Docker itself. The privileged worker must verify
the snapshot manifest, signed admission, stop and journal before execution.
"""
import hashlib
import re
from pathlib import Path
from .change_plan import ApprovedPlan
from .worker_snapshot import prepare_readonly_snapshot
from .snapshot_reverification import verify_snapshot_before_execution

_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def run_generated_code_tests(*, job_id, plan, staging_root,
                             snapshot_root, require_running, trusted_execute):
    if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise ValueError("Invalid job identity")
    if not isinstance(plan, ApprovedPlan) or not plan.changes:
        raise PermissionError("Approved change plan required")
    if not callable(require_running) or not callable(trusted_execute):
        raise PermissionError("Trusted stop and executor required")
    root = Path(staging_root)
    snapshots = Path(snapshot_root)
    if any(not p.is_absolute() or p.is_symlink() or not p.is_dir() or p.resolve() != p
           for p in (root, snapshots)):
        raise PermissionError("Invalid staging roots")
    # Never report a passing smoke test for code that is not exercised.
    # Only self-contained Python test proposals are supported by this adapter.
    files = {change.path: change.content for change in plan.changes}
    if not any(p.startswith("tests/test_") and p.endswith(".py") for p in files):
        raise PermissionError("Generated changes must include executable tests")
    if any(not p.endswith(".py") or not (p.startswith("tests/") or p.startswith("agent/"))
           for p in files):
        raise PermissionError("Only Python source and tests supported")
    # A test-only snapshot cannot validate modifications to existing repo
    # modules without their dependencies. Reject those proposals for now.
    if any(p.startswith("agent/") for p in files):
        raise PermissionError("Repository source changes require verified checkout snapshot")
    source = root / job_id
    if source.exists() or source.is_symlink():
        raise PermissionError("Staging job already exists")
    require_running()
    source.mkdir(mode=0o700)
    expected = {}
    for name, content in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        expected[name] = hashlib.sha256(content.encode()).hexdigest()
    snapshot = snapshots / job_id
    require_running()
    prepare_readonly_snapshot(str(source), str(snapshot), expected_files=expected)
    verify_snapshot_before_execution(str(snapshot), expected)
    require_running()
    result = trusted_execute(job_id=job_id, snapshot=str(snapshot),
                             snapshot_root=str(snapshots),
                             expected_hashes=expected)
    if (not isinstance(result, dict) or result.get("state") != "passed"
            or result.get("cleanup_verified") is not True):
        return {"state": "blocked", "cleanup_verified": False}
    return {"state": "passed", "cleanup_verified": True}
