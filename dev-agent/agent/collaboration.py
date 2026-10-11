"""Two-model proposal/review orchestration; provider calls are injected.

No network, GitHub writes, code execution, or deployment in this module.
The caller must enforce persistent emergency stop and budget reservations
before enabling real provider transports.
"""
import json
from dataclasses import dataclass
from .workers import fingerprint
from .review_validation import validate_review

@dataclass(frozen=True)
class CollaborationResult:
    proposal_sha256: str
    approved_by_reviewer: bool
    findings: tuple[str, ...]
    state: str

def collaborate(task: str, coder, reviewer) -> CollaborationResult:
    if not isinstance(task,str) or not 1 <= len(task.strip()) <= 4000:
        raise ValueError("Invalid task")
    if not callable(coder) or not callable(reviewer):
        raise ValueError("Worker callbacks required")
    proposal=coder(task)
    digest=fingerprint(proposal)
    # Reviewer must receive exact proposal and its fingerprint.
    review_text=reviewer(task,proposal,digest)
    review=validate_review(review_text,digest)
    return CollaborationResult(
        proposal_sha256=digest,
        approved_by_reviewer=review.approved,
        findings=review.findings,
        state="approval_required" if review.approved else "blocked",
    )

def offline_demo(task: str) -> CollaborationResult:
    def coder(instruction):
        return json.dumps({"task":instruction,"proposal":"Mock only; no source changes"},sort_keys=True)
    def reviewer(instruction,proposal,digest):
        return json.dumps({"proposal_sha256":digest,"approved":True,
                           "findings":["Mock review only; human approval required"]})
    return collaborate(task,coder,reviewer)
