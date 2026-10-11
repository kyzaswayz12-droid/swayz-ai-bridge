"""Offline coding-job staging and integrity verification.

Does not execute code, contact providers, publish Git changes, or trade.
"""
from dataclasses import dataclass
from pathlib import Path
from .change_set import validate_change_set
from .staging_writer import stage_changes
from .staging_manifest import verify_staged_changes

@dataclass(frozen=True)
class StagedJob:
    job_id: str
    workspace: str
    manifest: dict
    state: str

def prepare_coding_job(parent: Path, job_id: str, changes: dict) -> StagedJob:
    validated=validate_change_set(changes)
    workspace=stage_changes(parent,job_id,validated)
    manifest=verify_staged_changes(workspace,validated)
    return StagedJob(job_id,str(workspace),manifest,"staged_verified")
