"""Stopped-agent proposal-only development review (no API, Docker or GitHub).

This accepts externally supplied model *text*, not provider credentials or live
transports. Test and operator-preparation boundary only: passing checks does not
authenticate the text as a provider response or authorise its execution.
A future authenticated dispatcher must independently enforce USD reservations.
"""
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .change_plan import validate_change_plan
from .collaboration_preflight import preflight
from .collaboration_cost_preview import preview_task
from .fx_approval import load_approved_gbp_per_usd
from .rate_card_loader import load_rate_card
from .review_validation import validate_review
from .secret_file import load_provider_keys

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_JOB = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def _readonly_rows(path, statement):
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise PermissionError("Authoritative ledger unavailable")
    with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        return db.execute(statement).fetchall()


def inspect_approvals(*, task, openai_card, claude_card, fx_card,
                      stop_db, gbp_budget_db, credentials_file,
                      maximum_usd=Decimal("0.05"),
                      now=None):
    """Read-only, fail-closed checks; STOP MUST stay engaged throughout."""
    if type(maximum_usd) is not Decimal or maximum_usd != Decimal("0.05"):
        raise PermissionError("Fixed USD authorisation required")
    if not isinstance(task, str) or not 1 <= len(task.strip()) <= 400:
        raise ValueError("Short, exact coding task required")
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware clock required")
    if _readonly_rows(stop_db, "SELECT stopped FROM agent_control WHERE id=1") != [(1,)]:
        raise PermissionError("Emergency stop must remain engaged")
    # Validates owner and exact permission mode; never prints or returns keys.
    keys = load_provider_keys(credentials_file)
    if set(keys) != {"OPENAI_API_KEY", "ANTHROPIC_API_KEY"}:
        raise PermissionError("Provider credentials incomplete")
    del keys
    a = load_rate_card(openai_card, "openai", "gpt-5-mini", today=now.date())
    b = load_rate_card(claude_card, "anthropic", "claude-haiku-4-5-20251001",
                       today=now.date())
    approved = preflight(task, openai_card=Path(openai_card),
                         claude_card=Path(claude_card))
    if approved["provider_calls"] != 0:
        raise PermissionError("Unexpected provider execution")
    estimate = preview_task(task)
    if estimate.total_reservation_usd > maximum_usd:
        raise PermissionError("USD reservation exceeds explicit limit")
    # Keep pricing identical to the owner-approved reference cards.
    from .reference_rates import reference_rate
    if a != reference_rate("openai", "gpt-5-mini") or b != reference_rate("anthropic", "claude-haiku-4-5-20251001"):
        raise PermissionError("Unapproved pricing")
    fx = load_approved_gbp_per_usd(fx_card, today=now.date())
    if fx <= 0:
        raise PermissionError("Invalid FX rate")
    rows = _readonly_rows(gbp_budget_db,
        "SELECT reserved_gbp,actual_gbp FROM gbp_reservations")
    # Conservatively include every outstanding hold, including older dates.
    used = sum((Decimal(actual if actual is not None else held)
                for held, actual in rows), Decimal("0"))
    planned = estimate.total_reservation_usd * fx
    if not planned.is_finite() or used < 0 or used + planned > Decimal("5.00"):
        raise PermissionError("GBP reservation limit exceeded")
    if _readonly_rows(stop_db, "SELECT stopped FROM agent_control WHERE id=1") != [(1,)]:
        raise PermissionError("Emergency stop changed during preflight")
    return {"state": "preflight_passed", "paid_calls": 0,
            "usd_reserved": str(estimate.total_reservation_usd),
            "gbp_equivalent": str(planned), "execution_authorised": False}


def review_proposal(*, job_id, task, base_sha, proposal_text, review_text,
                    approvals, checkpoint_dir):
    """Validate supplied structured proposal/review; create one isolated record.

    Does not contact GPT/Claude, assert response authenticity, modify queue,
    reserve costs, read signing keys, open the stop, or run Docker.
    """
    if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise ValueError("Invalid job ID")
    if not isinstance(base_sha, str) or not _SHA.fullmatch(base_sha):
        raise ValueError("Invalid approved base")
    if not isinstance(approvals, dict) or approvals.get("state") != "preflight_passed" or approvals.get("paid_calls") != 0:
        raise PermissionError("Preflight required")
    if not isinstance(task, str) or not 1 <= len(task.strip()) <= 400:
        raise ValueError("Task required")
    try:
        raw = json.loads(proposal_text)
        if not isinstance(raw, dict) or set(raw) != {"base_sha", "branch", "changes", "proposal_sha256"}:
            raise ValueError("Invalid structured proposal")
        canonical = json.dumps({k: v for k, v in raw.items()
                                if k != "proposal_sha256"},
                               sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        digest = hashlib.sha256(canonical.encode("ascii")).hexdigest()
        # Caller cannot select arbitrary digest; recompute, then check model text.
        if raw["proposal_sha256"] != digest:
            raise ValueError("Proposal digest mismatch")
        plan = validate_change_plan(proposal_text, approved_base_sha=base_sha,
                                    approved_proposal_sha256=digest)
        verified = validate_review(review_text, digest)
    except (ValueError, TypeError, UnicodeError, KeyError) as exc:
        raise PermissionError("Proposal or independent review invalid") from exc
    if not verified.approved:
        raise PermissionError("Independent review rejected")
    # Restrict this first experiment to a new self-contained Python test.
    if len(plan.changes) != 1 or not re.fullmatch(r"tests/test_[a-z0-9_]+\.py", plan.changes[0].path):
        raise PermissionError("Only a single Python test file permitted")
    folder = Path(checkpoint_dir)
    if not folder.is_absolute() or folder.is_symlink() or not folder.is_dir():
        raise PermissionError("Existing private output directory required")
    if os.stat(folder).st_mode & 0o077:
        raise PermissionError("Output directory must be private")
    output = folder / (job_id + "-reviewed.json")
    record = {
        "job_id": job_id, "task": task, "base_sha": base_sha,
        "proposal_sha256": digest, "proposal": raw,
        "review": json.loads(review_text), "state": "operator_review_required",
        "model_responses_authenticated": False,
        "paid_calls": 0, "execution_authorised": False,
        "github_writes": 0, "docker_executed": False,
    }
    fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(record, stream, sort_keys=True)
    return {"state": "operator_review_required", "job_id": job_id,
            "proposal_sha256": digest, "checkpoint": str(output),
            "paid_calls": 0, "execution_authorised": False}
