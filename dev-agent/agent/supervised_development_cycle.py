"""Supervised development-cycle coordinator using existing Swayz components.

The caller supplies already-authorised, independently validated provider
responses and a trusted Docker job runner. This coordinator never creates
credentials, makes paid API calls, bypasses the stop or merges a PR.
"""
import json
import hashlib
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
        # A separately tested repair must never silently publish the original\n        # plan. Require independently reviewed, digest-bound replacement.\n        delivery_raw = coding_response\n        delivery_digest = approved_proposal_sha256\n        if "repair_delivery" in test_result:\n            repair = test_result["repair_delivery"]\n            if (not isinstance(repair, dict) or set(repair) !=\n                    {"raw_plan", "review_response", "proposal_sha256"}):\n                raise PermissionError("Invalid reviewed repair delivery")\n            try:
                repair_doc = json.loads(repair["raw_plan"])
                canonical = json.dumps({k: v for k, v in repair_doc.items()
                                        if k != "proposal_sha256"},
                                       sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                calculated = hashlib.sha256(canonical.encode("ascii")).hexdigest()
            except (ValueError, TypeError, UnicodeError, AttributeError):
                raise PermissionError("Invalid canonical repair proposal") from None
            if calculated != repair["proposal_sha256"]:
                raise PermissionError("Repair digest does not match proposal content")
            revised = validate_change_plan(\n                repair["raw_plan"], approved_base_sha=approved_base_sha,\n                approved_proposal_sha256=repair["proposal_sha256"])\n            if revised.proposal_sha256 == plan.proposal_sha256:\n                raise PermissionError("Repair must have distinct proposal identity")\n            try:\n                revised_review = json.loads(repair["review_response"])\n            except (TypeError, ValueError):\n                raise PermissionError("Invalid independent repair review") from None\n            if (not isinstance(revised_review, dict) or\n                    set(revised_review) != {"proposal_sha256", "approved", "findings"} or\n                    revised_review["proposal_sha256"] != revised.proposal_sha256 or\n                    revised_review["approved"] is not True or\n                    not isinstance(revised_review["findings"], list) or\n                    any(not isinstance(x, str) or not x.strip() for x in revised_review["findings"])):\n                raise PermissionError("Repair proposal not independently approved")\n            delivery_raw = repair["raw_plan"]\n            delivery_digest = revised.proposal_sha256\n        require_running()\n        pr = deliver_approved_draft(
            raw_plan=delivery_raw,
            approved_base_sha=approved_base_sha,
            approved_proposal_sha256=delivery_digest,
            base_branch=base_branch, github=github,
            require_running=require_running)
        task_queue.finish(job_id, "done")
        return DevelopmentCycleResult(job_id, "done", pr)
    except BaseException:
        task_queue.finish(job_id, "blocked")
        raise
