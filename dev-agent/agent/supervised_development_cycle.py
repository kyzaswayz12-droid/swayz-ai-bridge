"""Supervised development-cycle coordinator using existing Swayz components.

The caller supplies already-authorised, independently validated provider
responses and a trusted Docker job runner. This coordinator never creates
credentials, makes paid API calls, bypasses the stop or merges a PR.
"""
import json
from dataclasses import dataclass
from .change_plan import validate_change_plan
from .draft_pr_delivery import deliver_approved_draft


@dataclass(frozen=True)
class DevelopmentCycleResult:
    job_id: str
    state: str
    draft_pr: dict | None = None


def complete_supervised_cycle(*, job_id, task_queue, require_running,
                              approved_base_sha, approved_proposal_sha256,
                              base_branch, coding_response, review_response,
                              run_verified_tests, github):
    if not callable(require_running) or not callable(run_verified_tests):
        raise PermissionError("Trusted stop and Docker runner required")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("Job identity required")
    # This is a pre-admitted queue item, not a new job slot.
    require_running()
    row = task_queue.get(job_id)
    if not isinstance(row, dict) or row.get("state") != "queued":
        raise PermissionError("Development task not queued")
    if not isinstance(row.get("task"), str) or not row["task"].strip():
        raise PermissionError("Invalid queued task")
    # The caller must supply authenticated model outputs from a separately
    # budget-reserved dispatcher. This function cannot contact providers.
    if not isinstance(coding_response, str) or not isinstance(review_response, str):
        raise PermissionError("Validated provider responses required")
    plan = validate_change_plan(coding_response,
        approved_base_sha=approved_base_sha,
        approved_proposal_sha256=approved_proposal_sha256)
    try:
        review = json.loads(review_response)
    except (ValueError, TypeError):
        raise PermissionError("Invalid review response") from None
    if (not isinstance(review, dict)
            or set(review) != {"proposal_sha256", "approved", "findings"}
            or review["proposal_sha256"] != plan.proposal_sha256
            or review["approved"] is not True
            or not isinstance(review["findings"], list)
            or any(not isinstance(x, str) or not x.strip() for x in review["findings"])):
        raise PermissionError("Independent proposal review not approved")
    require_running()
    # Claim atomically; no retry on a partially completed job.
    if not task_queue.claim(job_id):
        raise PermissionError("Job already claimed")
    try:
        require_running()
        test_result = run_verified_tests(job_id=job_id, plan=plan)
        if (not isinstance(test_result, dict)
                or test_result.get("state") != "passed"
                or test_result.get("cleanup_verified") is not True):
            task_queue.finish(job_id, "blocked")
            return DevelopmentCycleResult(job_id, "blocked")
        require_running()
        pr = deliver_approved_draft(
            raw_plan=coding_response,
            approved_base_sha=approved_base_sha,
            approved_proposal_sha256=approved_proposal_sha256,
            base_branch=base_branch, github=github,
            require_running=require_running)
        task_queue.finish(job_id, "done")
        return DevelopmentCycleResult(job_id, "done", pr)
    except BaseException:
        task_queue.finish(job_id, "blocked")
        raise
