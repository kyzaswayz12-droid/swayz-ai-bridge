"""Offline verified handoff; no Docker execution or GitHub writes."""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from .staging_manifest import verify_staged_changes

@dataclass(frozen=True)
class TestHandoff:
    job_id: str
    workspace: str
    manifest_sha256: str
    state: str

def prepare_test_handoff(job_id, workspace, changes):
    if not isinstance(job_id,str) or not job_id.isascii() or not 1<=len(job_id)<=64 or not all(c.isalnum() or c in "-_" for c in job_id):
        raise ValueError("Invalid job ID")
    workspace=Path(workspace)
    if workspace.name!=job_id:
        raise ValueError("Workspace/job mismatch")
    manifest=verify_staged_changes(workspace,changes)
    digest=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return TestHandoff(job_id,str(workspace),digest,"awaiting_trusted_worker")
