"""Safe one-shot real collaboration remains deliberately gated.

The paired workflow can be tested offline. Real provider calls must be
individually budget-reserved and recorded before this layer can be activated.
Never treat a model's JSON approval as the owner's approval.
"""
from .collaboration import offline_demo

def staging_result(task: str) -> dict:
    result=offline_demo(task)
    return {
        "state":result.state,
        "proposal_sha256":result.proposal_sha256,
        "reviewer_approved":result.approved_by_reviewer,
        "findings":list(result.findings),
        "provider_calls":0,
        "github_writes":0,
        "live_trading":False,
    }
