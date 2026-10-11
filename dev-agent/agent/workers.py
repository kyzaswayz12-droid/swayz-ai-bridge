"""Offline deterministic development worker simulator.

No network calls, subprocesses, GitHub writes or provider API calls.
"""
import hashlib
import json
from dataclasses import dataclass
from .core import State, TaskStore

@dataclass(frozen=True)
class Proposal:
    task_id: str
    content: str
    sha256: str

@dataclass(frozen=True)
class Review:
    proposal_sha256: str
    approved: bool
    summary: str

def fingerprint(content: str) -> str:
    if not isinstance(content,str) or not content or len(content.encode()) > 65536:
        raise ValueError("Invalid proposal")
    return hashlib.sha256(content.encode()).hexdigest()

def process_one(store: TaskStore, coder, reviewer):
    """Claim one task and record review outcome. Explicit human approval remains mandatory."""
    row=store.claim_next()
    if row is None:
        return None
    task_id,title=row
    try:
        content=coder(task_id,title)
        proposal=Proposal(task_id,content,fingerprint(content))
        store.transition(task_id,State.CLAIMED,State.CODE_READY)
        store.transition(task_id,State.CODE_READY,State.REVIEW_REQUIRED)
        review=reviewer(proposal)
        if not isinstance(review,Review) or review.proposal_sha256 != proposal.sha256:
            raise ValueError("Review does not match proposal")
        if not review.approved or not review.summary.strip():
            store.transition(task_id,State.REVIEW_REQUIRED,State.BLOCKED)
            return {"task_id":task_id,"state":"blocked","reason":"review_rejected"}
        store.transition(task_id,State.REVIEW_REQUIRED,State.APPROVAL_REQUIRED)
        return {"task_id":task_id,"state":"approval_required",
                "proposal_sha256":proposal.sha256,"review":review.summary}
    except Exception:
        current=store.db.execute("SELECT state FROM tasks WHERE task_id=?",(task_id,)).fetchone()
        if current and current[0] in (State.CLAIMED.value,State.CODE_READY.value,State.REVIEW_REQUIRED.value):
            store.transition(task_id,State(current[0]),State.BLOCKED)
        raise

def demo(store: TaskStore):
    return process_one(store,
        lambda task_id,title: json.dumps({"task":task_id,"title":title,"change":"mock-only"},sort_keys=True),
        lambda proposal: Review(proposal.sha256,True,"Mock review only; human approval required"))
