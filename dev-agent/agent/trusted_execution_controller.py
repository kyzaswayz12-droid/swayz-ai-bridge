"""Offline trusted execution decision. Never starts Docker or executes code."""
from dataclasses import dataclass
from .trusted_worker_gate import verify_and_admit

@dataclass(frozen=True)
class ExecutionDecision:
    state: str
    job_id: str
    docker_executed: bool = False

def authorise_test_job(inbox, raw, signature, secret, *, job_id, workspace, changes):
    accepted=verify_and_admit(inbox,raw,signature,secret,
                              job_id=job_id,workspace=workspace,changes=changes)
    return ExecutionDecision("accepted_for_supervised_execution" if accepted else "duplicate_rejected",job_id)
