"""Restricted draft-only GitHub delivery of an already approved change plan.

The caller supplies a narrowly permissioned GitHub adapter; no tokens are
accepted here. This does not merge, deploy, or call AI providers.
"""
from .change_plan import ApprovedPlan, validate_change_plan
from .github_preflight import prepare_draft_pr


def deliver_approved_draft(*, raw_plan: str, approved_base_sha: str,
                           approved_proposal_sha256: str, base_branch: str,
                           github, require_running):
    if not callable(require_running):
        raise PermissionError("Authoritative emergency-stop check required")
    if getattr(github, "swayz_draft_only", False) is not True:
        raise PermissionError("Restricted draft-only GitHub adapter required")
    plan = validate_change_plan(raw_plan,
        approved_base_sha=approved_base_sha,
        approved_proposal_sha256=approved_proposal_sha256)
    repo = "kyzaswayz12-droid/swayz-ai-bridge"
    require_running()
    draft = prepare_draft_pr(plan, repository=repo, base_branch=base_branch,
        read_branch_head=github.read_branch_head,
        branch_exists=github.branch_exists)
    # Recheck immediately before each GitHub write. A stop can occur between
    # actions; partial branches are left for explicit recovery, never merged.
    require_running()
    github.create_branch(repo, draft.head_branch, draft.base_sha)
    for change in plan.changes:
        require_running()
        github.put_new_file(repo, draft.head_branch, change.path, change.content)
    require_running()
    pr = github.create_pull_request(repo, base_branch=draft.base_branch,
        head_branch=draft.head_branch,
        title="Swayz agent proposal " + draft.proposal_sha256[:12],
        body="Automated development proposal. Review required; no merge or deployment.\n\nProposal SHA-256: " + draft.proposal_sha256,
        draft=True)
    if not isinstance(pr, dict) or pr.get("draft") is not True:
        raise PermissionError("Draft PR creation not confirmed")
    return pr
