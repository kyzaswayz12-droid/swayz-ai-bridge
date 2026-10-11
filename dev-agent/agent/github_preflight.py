"""Read-only preflight for a GitHub draft pull request."""
from dataclasses import dataclass
from .change_plan import ApprovedPlan

@dataclass(frozen=True)
class DraftPR:
    repository: str
    base_branch: str
    base_sha: str
    head_branch: str
    proposal_sha256: str
    files: tuple[str,...]

def prepare_draft_pr(plan: ApprovedPlan, *, repository: str,
                     base_branch: str, read_branch_head, branch_exists) -> DraftPR:
    if repository!="kyzaswayz12-droid/swayz-ai-bridge":
        raise ValueError("Repository not allowed")
    if base_branch not in ("main","feature/swayz-autonomous-dev-agent"):
        raise ValueError("Base branch not allowed")
    if read_branch_head(repository,base_branch)!=plan.base_sha:
        raise ValueError("Base branch changed; re-review required")
    if branch_exists(repository,plan.branch):
        raise ValueError("Agent branch already exists")
    return DraftPR(repository,base_branch,plan.base_sha,plan.branch,
                   plan.proposal_sha256,tuple(change.path for change in plan.changes))
