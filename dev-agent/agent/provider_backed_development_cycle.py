"""Supervised provider-backed development cycle.

Uses the existing paid one-shot dispatcher and the existing reviewed Docker /
draft-PR coordinator. Does not run automatically or enable paid calls itself.
"""
import hashlib
import json
from datetime import datetime
from decimal import Decimal

from .change_plan import validate_change_plan
from .reserved_provider_dispatch import dispatch_reserved_provider_once
from .supervised_development_cycle import complete_supervised_cycle


def run_provider_backed_cycle(
    *, job_id, task_queue, require_running, job_db, budget_db,
    control_db, fx_approval_path, now: datetime, base_branch, base_sha,
    openai_model, anthropic_model, openai_key, anthropic_key,
    openai_maximum_usd: Decimal, anthropic_maximum_usd: Decimal,
    run_verified_tests, github, owner_approved=False,
    paid_calls_enabled=False, transport=None,
):
    if owner_approved is not True or paid_calls_enabled is not True:
        raise PermissionError("Paid development not authorised")
    require_running()
    row = task_queue.get(job_id)
    if not isinstance(row, dict) or row.get("state") != "queued":
        raise PermissionError("Task must be durably queued")
    task = row["task"]
    # Deterministic IDs ensure uncertain network failures cannot be retried
    # with a fresh billing reservation.
    ids = (job_id + "-openai", job_id + "-anthropic")
    common = dict(job_db=job_db, budget_db=budget_db, control_db=control_db,
                  fx_approval_path=fx_approval_path, job_id=job_id, now=now,
                  owner_approved=True, paid_calls_enabled=True)
    if transport is not None:
        common["transport"] = transport
    coding = dispatch_reserved_provider_once(
        **common, request_id=ids[0], provider="openai",
        model=openai_model, api_key=openai_key,
        instruction="Return only JSON with base_sha, branch, changes, proposal_sha256. The server will replace proposal_sha256 with a verified SHA256 of canonical JSON for the other fields. No deployment or secrets.",
        task="Base SHA: " + base_sha + "\nTask: " + task,
        maximum_usd=openai_maximum_usd).response.text
    require_running()
    # The proposal identifier is supplied by the coding model but the review
    # must bind to the exact approved base SHA and that same identifier.
    proposal = json.loads(coding)
    if not isinstance(proposal, dict):
        raise PermissionError("Invalid coding proposal")
    digest = proposal.get("proposal_sha256")
    # Bind the review identity to actual proposal bytes, not a model-chosen
    # arbitrary identifier that could also appear in a different proposal.
    if not isinstance(digest, str):
        raise PermissionError("Proposal digest missing")
    canonical = json.dumps({k: v for k, v in proposal.items()
                            if k != "proposal_sha256"},
                           sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("ascii")).hexdigest()
    proposal["proposal_sha256"] = digest
    coding = json.dumps(proposal, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    validate_change_plan(coding, approved_base_sha=base_sha,
                         approved_proposal_sha256=digest)
    review = dispatch_reserved_provider_once(
        **common, request_id=ids[1], provider="anthropic",
        model=anthropic_model, api_key=anthropic_key,
        instruction="Review this change plan. Return only JSON: proposal_sha256, approved boolean, findings string array. Reject unsafe changes.",
        task=coding, maximum_usd=anthropic_maximum_usd).response.text
    require_running()
    return complete_supervised_cycle(
        job_id=job_id, task_queue=task_queue,
        require_running=require_running, approved_base_sha=base_sha,
        approved_proposal_sha256=digest, base_branch=base_branch,
        coding_response=coding, review_response=review,
        run_verified_tests=run_verified_tests, github=github)
