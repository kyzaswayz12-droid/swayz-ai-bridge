"""Split-authority provider grant contract (development-only, no live dispatch).

Root authority alone may reserve in the existing GBP ledger and sign a grant.
The unprivileged worker verifies the signature and claims a one-use job marker.
Neither role can sign executor jobs, open the emergency stop, or run Docker.
Live network transport is deliberately NOT implemented by this module.
"""
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .collaboration_cost_preview import preview_task
from .fx_approval import load_approved_gbp_per_usd
from .gbp_budget import GBPBudget
from .rate_card_loader import load_rate_card
from .reference_rates import reference_rate
from .secret_file import load_provider_keys

JOB_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
MODELS = ("gpt-5-mini", "claude-haiku-4-5-20251001")
TASK = ("Create a Python development-job label validator and unit tests. "
        "Accept lowercase letters, digits and hyphens, 1 to 32 characters. "
        "Reject whitespace, path traversal and invalid characters. Return "
        "a structured JSON code-change proposal. Do not modify executor, "
        "credentials, security controls or trading code.")
MAX_USD = Decimal("0.05")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _clock(now):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise PermissionError("Timezone-aware clock required")
    return now.astimezone(timezone.utc)


def _private_dir(path):
    folder = Path(path)
    st = folder.stat()
    if (not folder.is_absolute() or folder.is_symlink() or not folder.is_dir()
            or st.st_mode & 0o077):
        raise PermissionError("Private directory required")
    return folder


def _write_once(path, data):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        raise


def issue_split_grant(*, job_id, base_sha, openai_card, claude_card,
                      fx_card, gbp_budget_db, require_stop_engaged,
                      verify_owner, signing_key, now, output_directory):
    """Root operator boundary. Signed proof is issued only after BOTH holds.

    The injected root-owned signing key must be dedicated to provider grants:
    never pass Swayz's Docker executor signing key into this API.
    """
    if os.geteuid() != 0 or not callable(verify_owner) or verify_owner(job_id) is not True:
        raise PermissionError("Independent root operator approval required")
    if not isinstance(signing_key, Ed25519PrivateKey):
        raise PermissionError("Dedicated Ed25519 provider-grant signer required")
    if not callable(require_stop_engaged):
        raise PermissionError("Authoritative stop check required")
    if not isinstance(job_id, str) or not JOB_RE.fullmatch(job_id):
        raise PermissionError("Invalid job identity")
    if not isinstance(base_sha, str) or not SHA_RE.fullmatch(base_sha):
        raise PermissionError("Pinned GitHub base commit required")
    now = _clock(now)
    directory = _private_dir(output_directory)
    budget_path = Path(gbp_budget_db)
    if not budget_path.is_absolute() or budget_path.is_symlink() or not budget_path.is_file():
        raise PermissionError("Existing authoritative GBP ledger required")
    for path, provider, model in (
        (openai_card, "openai", MODELS[0]), (claude_card, "anthropic", MODELS[1])
    ):
        approved = load_rate_card(path, provider, model, today=now.date())
        if approved != reference_rate(provider, model):
            raise PermissionError("Rate card mismatch")
    fx = load_approved_gbp_per_usd(fx_card, today=now.date())
    quote = preview_task(TASK)
    if quote.total_reservation_usd > MAX_USD:
        raise PermissionError("Explicit USD ceiling exceeded")
    require_stop_engaged()
    grant_path = directory / (job_id + ".grant.json")
    if grant_path.exists() or grant_path.is_symlink():
        raise PermissionError("Grant already exists")
    ids = [job_id + "-openai", job_id + "-anthropic"]
    ledger = GBPBudget(str(budget_path))
    try:
        # Existing atomic per-request reservation prevents duplicate charge.
        # Uncertain failure deliberately retains holds: no retry permitted.
        if not ledger.reserve(ids[0], "openai", quote.openai_reservation_usd, fx, now):
            raise PermissionError("OpenAI hold already recorded")
        if not ledger.reserve(ids[1], "anthropic", quote.claude_reservation_usd, fx, now):
            raise PermissionError("Claude hold already recorded")
    finally:
        ledger.close()
    require_stop_engaged()
    payload = {
        "version": 1, "purpose": "swayz-provider-only-proposal",
        "job_id": job_id, "base_sha": base_sha,
        "task_sha256": hashlib.sha256(TASK.encode("utf-8")).hexdigest(),
        "models": list(MODELS), "request_ids": ids,
        "reserved_usd": str(quote.total_reservation_usd),
        "reserved_gbp": str(quote.total_reservation_usd * fx),
        "issued_utc": now.isoformat(),
        "expires_utc": (now + timedelta(minutes=10)).isoformat(),
        "docker_authorised": False, "github_writes_authorised": False,
        "live_trading_authorised": False, "retries": 0,
    }
    signature = signing_key.sign(_canonical(payload)).hex()
    grant = {"payload": payload, "signature": signature}
    _write_once(grant_path, _canonical(grant))
    return {"state": "signed_grant_prepared", "path": str(grant_path),
            "job_id": job_id, "provider_calls": 0}


def consume_split_grant(*, grant_bytes, verification_key, expected_job_id,
                        expected_base_sha, credential_file, require_stop_engaged,
                        claimed_directory, now):
    """Unprivileged worker validates and consumes a grant; does NOT call API.

    Production invocation must supply an independently trustworthy stopped
    state verifier and a private, durable claim directory on the worker side.
    """
    if not isinstance(verification_key, Ed25519PublicKey):
        raise PermissionError("Dedicated public grant key required")
    if not isinstance(grant_bytes, bytes) or len(grant_bytes) > 16384:
        raise PermissionError("Invalid grant bytes")
    if not callable(require_stop_engaged):
        raise PermissionError("Trusted stop verifier required")
    now = _clock(now)
    try:
        document = json.loads(grant_bytes)
        if not isinstance(document, dict) or set(document) != {"payload", "signature"}:
            raise ValueError("Invalid grant schema")
        payload = document["payload"]
        signature = bytes.fromhex(document["signature"])
        verification_key.verify(signature, _canonical(payload))
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeError, Exception) as exc:
        raise PermissionError("Provider grant signature or schema invalid") from exc
    if (set(payload) != {
        "version", "purpose", "job_id", "base_sha", "task_sha256",
        "models", "request_ids", "reserved_usd", "reserved_gbp",
        "issued_utc", "expires_utc", "docker_authorised",
        "github_writes_authorised", "live_trading_authorised", "retries"
    } or payload["version"] != 1
        or payload["purpose"] != "swayz-provider-only-proposal"
        or payload["job_id"] != expected_job_id
        or payload["base_sha"] != expected_base_sha
        or not isinstance(expected_job_id, str) or not JOB_RE.fullmatch(expected_job_id)
        or not isinstance(expected_base_sha, str) or not SHA_RE.fullmatch(expected_base_sha)
        or payload["task_sha256"] != hashlib.sha256(TASK.encode()).hexdigest()
        or payload["models"] != list(MODELS)
        or payload["request_ids"] != [expected_job_id+"-openai", expected_job_id+"-anthropic"]
        or payload["docker_authorised"] is not False
        or payload["github_writes_authorised"] is not False
        or payload["live_trading_authorised"] is not False
        or payload["retries"] != 0):
        raise PermissionError("Grant not scoped to exact provider-only task")
    try:
        issued = datetime.fromisoformat(payload["issued_utc"])
        expiry = datetime.fromisoformat(payload["expires_utc"])
        usd = Decimal(payload["reserved_usd"])
        gbp = Decimal(payload["reserved_gbp"])
    except (ValueError, TypeError) as exc:
        raise PermissionError("Invalid grant amounts or timestamps") from exc
    if (_clock(issued) > now or _clock(expiry) < now
            or expiry - issued != timedelta(minutes=10)
            or not usd.is_finite() or usd != preview_task(TASK).total_reservation_usd
            or usd > MAX_USD or not gbp.is_finite() or gbp <= 0):
        raise PermissionError("Grant expired, premature or over limit")
    require_stop_engaged()
    keys = load_provider_keys(credential_file)
    if set(keys) != {"OPENAI_API_KEY", "ANTHROPIC_API_KEY"}:
        raise PermissionError("Incomplete credentials")
    del keys
    directory = _private_dir(claimed_directory)
    marker = directory / (expected_job_id + ".claimed")
    # A failed or interrupted attempt is final until an operator reconciles
    # the ledger. Never delete markers for retries.
    _write_once(marker, hashlib.sha256(grant_bytes).hexdigest().encode("ascii"))
    require_stop_engaged()
    return {"state": "claimed_for_operator_review", "job_id": expected_job_id,
            "provider_calls": 0, "live_dispatch_enabled": False,
            "retries": 0, "execution_authorised": False}
