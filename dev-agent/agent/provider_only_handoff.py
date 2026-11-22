"""Operator-only GPT -> Claude proposal handoff; never executes generated code.

No autonomous scheduler, GitHub writes, trading, Docker, job admission or
emergency-stop release. This uses the existing *GBP* reservation ledger, NOT
the older USD collaboration ledger. A unique journal file is created before
any reservation/call: uncertain failures must be reconciled, never retried.
"""
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .collaboration_cost_preview import preview_task
from .gbp_budget import GBPBudget
from .http_transport import provider_transport
from .providers import (
    prepare_openai_request, prepare_anthropic_request,
    openai_response, anthropic_response,
)
from .proposal_only_staging import inspect_approvals
from .review_validation import validate_review
from .change_plan import validate_change_plan
from .secret_file import load_provider_keys

_JOB = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
_SHA = re.compile(r"[a-f0-9]{40}\Z")
_TASK = ("Create a Python development-job label validator and unit tests. "
         "Accept lowercase letters, digits and hyphens, 1 to 32 characters. "
         "Reject whitespace, path traversal and invalid characters. Return "
         "a structured JSON code-change proposal. Do not modify executor, "
         "credentials, security controls or trading code.")
MAX_USD = Decimal("0.05")


def _stop_engaged(path):
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise PermissionError("Authoritative emergency stop unavailable")
    with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        if db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchall() != [(1,)]:
            raise PermissionError("Emergency stop must remain engaged")


def _write_once(path, obj):
    content = json.dumps(obj, sort_keys=True, ensure_ascii=True).encode("utf-8")
    if len(content) > 131072:
        raise PermissionError("Checkpoint too large")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _digest_bound_plan(raw_text, base_sha):
    doc = json.loads(raw_text)
    if not isinstance(doc, dict) or set(doc) != {
            "base_sha", "branch", "changes", "proposal_sha256"}:
        raise PermissionError("Unexpected coding proposal schema")
    canonical = json.dumps({k: v for k, v in doc.items()
                            if k != "proposal_sha256"},
                           sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("ascii")).hexdigest()
    # Recompute model-supplied hash; the reviewer will get the canonical
    # identity, not an untrusted arbitrary model claim.
    doc["proposal_sha256"] = digest
    fixed = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    plan = validate_change_plan(fixed, approved_base_sha=base_sha,
                                approved_proposal_sha256=digest)
    if len(plan.changes) != 1 or not re.fullmatch(
            r"tests/test_[a-z0-9_]+\.py", plan.changes[0].path):
        raise PermissionError("Only one self-contained Python test permitted")
    return fixed, digest


def run_provider_only(*, job_id, base_sha, checkpoint_dir, openai_card,
                      claude_card, fx_card, credentials_file, stop_db,
                      gbp_budget_db, owner_authorised=False,
                      paid_calls_enabled=False, transport=provider_transport,
                      test_mode=False, now=None):
    """At most one request per provider and no retries.

    Only the operator-authenticated host should invoke this. Real transport is
    allowed only with explicit two-factor boolean approval. Tests may supply a
    fake transport in test_mode; resulting records say they are simulated.
    """
    if owner_authorised is not True or paid_calls_enabled is not True:
        raise PermissionError("Explicit provider-only owner approval required")
    if transport is not provider_transport and test_mode is not True:
        raise PermissionError("Custom live provider transport rejected")
    if not callable(transport):
        raise PermissionError("Provider transport invalid")
    if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise ValueError("Invalid new proposal ID")
    if not isinstance(base_sha, str) or not _SHA.fullmatch(base_sha):
        raise ValueError("Approved base commit required")
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("UTC clock required")

    root = Path(checkpoint_dir)
    if (not root.is_absolute() or root.is_symlink() or not root.is_dir()
            or (root.stat().st_mode & 0o077)):
        raise PermissionError("Protected existing checkpoint directory required")
    budget = Path(gbp_budget_db)
    if not budget.is_absolute() or budget.is_symlink() or not budget.is_file():
        raise PermissionError("Existing GBP budget ledger required")

    approvals = inspect_approvals(
        task=_TASK, openai_card=openai_card, claude_card=claude_card,
        fx_card=fx_card, credentials_file=credentials_file, stop_db=stop_db,
        gbp_budget_db=gbp_budget_db, maximum_usd=MAX_USD, now=now)
    quote = preview_task(_TASK)
    if quote.total_reservation_usd > MAX_USD or approvals["usd_reserved"] != str(quote.total_reservation_usd):
        raise PermissionError("USD authorisation mismatch")

    # The marker prevents double spending even on a crash between two
    # budget reservations. Never delete or reset it to repeat a failed call.
    prefix = root / job_id
    _write_once(root / (job_id + ".started.json"), {
        "job_id": job_id, "base_sha": base_sha, "task": _TASK,
        "started_utc": now.astimezone(timezone.utc).isoformat(),
        "status": "started", "paid_calls": "unconfirmed",
        "model_responses_authenticated": False,
    })

    fx = Decimal(approvals["gbp_equivalent"]) / quote.total_reservation_usd
    budget_store = GBPBudget(str(budget))
    request_ids = [job_id + "-openai", job_id + "-anthropic"]
    try:
        # Both conservative holds must succeed before ANY network attempt.
        if not budget_store.reserve(request_ids[0], "openai",
                                    quote.openai_reservation_usd, fx, now):
            raise PermissionError("OpenAI reservation already present")
        if not budget_store.reserve(request_ids[1], "anthropic",
                                    quote.claude_reservation_usd, fx, now):
            raise PermissionError("Claude reservation already present")
    finally:
        budget_store.close()

    keys = load_provider_keys(credentials_file)
    _stop_engaged(stop_db)
    coder_prompt = (
        "Return ONLY JSON with base_sha, branch, changes, proposal_sha256. "
        "Set base_sha to " + base_sha + ". Make exactly one new file at "
        "tests/test_job_label.py with self-contained runnable Python unit "
        "tests for a label validator. No existing source-file edits; "
        "no remote calls, credentials, trading, deployment or executor edits."
    )
    raw = transport("openai",
        prepare_openai_request("gpt-5-mini", coder_prompt, _TASK,
                               max_output_tokens=1024),
        keys["OPENAI_API_KEY"])
    # A completed transport attempt is recorded before parsing, so any
    # malformed response is auditable, and never retried.
    _write_once(root / (job_id + ".openai-response.json"), {
        "job_id": job_id, "provider": "openai",
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_response_hex": raw.hex(), "simulated": bool(test_mode),
        "request_id": request_ids[0],
    })
    result = openai_response(raw)
    coding, digest = _digest_bound_plan(result.text, base_sha)
    _stop_engaged(stop_db)
    review_prompt = json.dumps({"task": _TASK, "coding_proposal": json.loads(coding),
                                "proposal_sha256": digest},
                               separators=(",", ":"), sort_keys=True)
    if len(review_prompt.encode()) > 12000:
        raise PermissionError("Review input too large")
    review_instruction = (
        "Independently review this exact Python change proposal. Reply ONLY "
        "with JSON: proposal_sha256, approved (boolean), findings (string array). "
        "Reject insecure, untested or unsupported changes; never rewrite the hash.")
    raw_review = transport("anthropic",
        prepare_anthropic_request("claude-haiku-4-5-20251001",
                                  review_instruction, review_prompt,
                                  max_tokens=512, structured_review=True),
        keys["ANTHROPIC_API_KEY"])
    _write_once(root / (job_id + ".claude-response.json"), {
        "job_id": job_id, "provider": "anthropic",
        "response_sha256": hashlib.sha256(raw_review).hexdigest(),
        "raw_response_hex": raw_review.hex(), "simulated": bool(test_mode),
        "request_id": request_ids[1],
    })
    review = anthropic_response(raw_review)
    verified = validate_review(review.text, digest)
    _stop_engaged(stop_db)
    _write_once(root / (job_id + ".result.json"), {
        "job_id": job_id, "proposal_sha256": digest,
        "state": "operator_review_required" if verified.approved else "review_rejected",
        "review_approved": verified.approved,
        "findings": list(verified.findings),
        "simulated": bool(test_mode),
        "provider_transport_used": not test_mode,
        "execution_authorised": False, "github_writes": 0,
        "docker_executed": False, "billing_verified": False,
        "reserved_usd": str(quote.total_reservation_usd),
        "openai_usage": [result.input_tokens, result.output_tokens],
        "claude_usage": [review.input_tokens, review.output_tokens],
    })
    return {"state": "operator_review_required" if verified.approved else "review_rejected",
            "job_id": job_id, "proposal_sha256": digest, "paid_calls": 0 if test_mode else 2,
            "execution_authorised": False, "checkpoint_dir": str(root)}
