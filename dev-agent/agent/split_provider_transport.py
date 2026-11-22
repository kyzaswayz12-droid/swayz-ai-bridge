"""Split-authority grant transfer and bounded provider-only transport.

Root publishes an existing signed grant into a private root-controlled inbox.
The swayzdev worker consumes it once. Each model call requires a fresh,
privileged, signed STOP-engaged proof bound to the grant and request phase.
No Docker, GitHub writes, trading or emergency-stop release exists here.

An operator-controlled stop-proof IPC service must be provisioned and reviewed
before live deployment. This module neither installs nor starts such a service.
"""
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .split_provider_authority import (
    _canonical, _clock, _private_dir, _write_once, consume_split_grant,
    TASK, MODELS,
)
from .providers import (
    prepare_openai_request, prepare_anthropic_request, openai_response,
    anthropic_response,
)
from .http_transport import provider_transport
from .secret_file import load_provider_keys
from .review_validation import validate_review
from .change_plan import validate_change_plan

PHASES = ("openai", "anthropic")
_SHA = re.compile(r"[a-f0-9]{40}\Z")


def _read_regular(path, limit):
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise PermissionError("Required protected file absent or unsafe")
    if p.stat().st_size > limit:
        raise PermissionError("Oversized protected file")
    return p.read_bytes()


def publish_split_grant(*, source, inbox, job_id, worker_group, require_stop_engaged):
    """Root-only transfer. Pre-provisioned inbox: root:swayzdev mode 0750.

    Never alters an existing grant, signing key, credential, database or stop.
    The 0640 copy is the ONLY cross-account material. Must not share a writable
    directory with the unprivileged worker.
    """
    import grp
    from .split_provider_authority import JOB_RE
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    if not isinstance(job_id, str) or not JOB_RE.fullmatch(job_id):
        raise PermissionError("Invalid grant identity")
    if worker_group != "swayzdev":
        raise PermissionError("Only the existing swayzdev group is approved")
    if not callable(require_stop_engaged):
        raise PermissionError("Trusted stop check required")
    folder = Path(inbox)
    st = folder.stat()
    group_id = grp.getgrnam(worker_group).gr_gid
    if (not folder.is_absolute() or folder.is_symlink()
            or not folder.is_dir() or st.st_uid != 0
            or st.st_gid != group_id or st.st_mode & 0o777 != 0o750):
        raise PermissionError("Dedicated root-owned grant inbox required")
    src = Path(source)
    if src.name != job_id + ".grant.json" or src.is_symlink():
        raise PermissionError("Incorrect source grant")
    if src.stat().st_mode & 0o077:
        raise PermissionError("Source grant not private")
    data = _read_regular(src, 16384)
    # A well-formed signed grant should be transferred unchanged; signature
    # verification is independently performed by the unprivileged worker.
    require_stop_engaged()
    dest = folder / src.name
    fd = os.open(str(dest), os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        os.fchown(stream.fileno(), 0, group_id)
        os.fchmod(stream.fileno(), 0o640)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    require_stop_engaged()
    return {"state": "grant_published", "job_id": job_id,
            "grant_sha256": hashlib.sha256(data).hexdigest(),
            "provider_calls": 0}


def issue_stop_proof(*, job_id, phase, grant_bytes, stop_db,
                     signing_key, now):
    """Root authority: prove the stop is engaged at this instant.

    A separate authenticated privileged boundary must call this for each
    phase. Proofs are valid for at most 15 seconds and are request-specific.
    """
    if os.geteuid() != 0 or not isinstance(signing_key, Ed25519PrivateKey):
        raise PermissionError("Dedicated root grant signer required")
    from .split_provider_authority import JOB_RE
    if not isinstance(job_id, str) or not JOB_RE.fullmatch(job_id) or phase not in PHASES:
        raise PermissionError("Invalid proof request")
    if not isinstance(grant_bytes, bytes) or len(grant_bytes) > 16384:
        raise PermissionError("Invalid grant")
    now = _clock(now)
    p = Path(stop_db)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise PermissionError("Stop database missing")
    with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        if db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchall() != [(1,)]:
            raise PermissionError("Emergency stop not engaged")
    claim = {
        "purpose": "provider-only-stop-proof-v1", "job_id": job_id,
        "phase": phase, "grant_sha256": hashlib.sha256(grant_bytes).hexdigest(),
        "issued_utc": now.isoformat(),
        "expires_utc": (now + timedelta(seconds=15)).isoformat(),
        "stopped": True,
    }
    return _canonical({"claim": claim,
                       "signature": signing_key.sign(_canonical(claim)).hex()})


def _verify_stop_proof(*, proof, grant_bytes, job_id, phase, public_key, now):
    if not isinstance(public_key, Ed25519PublicKey) or not isinstance(proof, bytes) or len(proof) > 4096:
        raise PermissionError("Invalid proof input")
    try:
        d = json.loads(proof)
        if set(d) != {"claim", "signature"} or not isinstance(d["claim"], dict):
            raise ValueError("Invalid proof schema")
        c = d["claim"]
        public_key.verify(bytes.fromhex(d["signature"]), _canonical(c))
        if (set(c) != {"purpose", "job_id", "phase", "grant_sha256",
                       "issued_utc", "expires_utc", "stopped"}
                or c["purpose"] != "provider-only-stop-proof-v1"
                or c["job_id"] != job_id or c["phase"] != phase
                or c["grant_sha256"] != hashlib.sha256(grant_bytes).hexdigest()
                or c["stopped"] is not True):
            raise ValueError("Proof identity mismatch")
        issued = _clock(datetime.fromisoformat(c["issued_utc"]))
        expiry = _clock(datetime.fromisoformat(c["expires_utc"]))
        now = _clock(now)
        if issued > now or expiry < now or expiry - issued != timedelta(seconds=15):
            raise ValueError("Stop proof not fresh")
    except (ValueError, TypeError, KeyError, InvalidSignature, AttributeError) as exc:
        raise PermissionError("Invalid signed stop proof") from exc


def run_signed_provider_handoff(*, job_id, base_sha, inbox, public_key,
                                credential_file, claimed_directory,
                                checkpoint_dir, get_fresh_stop_proof,
                                transport=provider_transport, simulated=False,
                                now=None):
    """One GPT request, then one Claude review; no retries or executor access.

    get_fresh_stop_proof(phase, grant_bytes) must obtain a newly minted root
    attestation from a separately authenticated privileged service. A caller
    supplied callback is NOT a substitute for that service's security: only
    the resulting Ed25519 signature is trusted.
    """
    if not callable(get_fresh_stop_proof):
        raise PermissionError("Privileged stop-proof provider required")
    if simulated is True and transport is provider_transport:
        raise PermissionError("Simulated mode requires an offline fake transport")
    if simulated is not True and transport is not provider_transport:
        raise PermissionError("Unapproved live transport")
    if not callable(transport):
        raise PermissionError("Invalid transport")
    clock_explicitly_supplied = now is not None
    if now is None:
        now = datetime.now(timezone.utc)
    now = _clock(now)
    if not isinstance(base_sha, str) or not _SHA.fullmatch(base_sha):
        raise PermissionError("Pinned base SHA required")
    _private_dir(claimed_directory)
    _private_dir(checkpoint_dir)
    grant_path = Path(inbox) / (job_id + ".grant.json")
    grant_bytes = _read_regular(grant_path, 16384)
    # STOP is independently attested before the claim and each provider call.
    def guard(phase):
        proof = get_fresh_stop_proof(phase, grant_bytes)
        _verify_stop_proof(proof=proof, grant_bytes=grant_bytes, job_id=job_id,
                           phase=phase, public_key=public_key,
                           now=now if clock_explicitly_supplied else datetime.now(timezone.utc))
    guard("openai")
    # consume_split_grant already validates signature, TTL, task, identities,
    # credential ownership and writes the permanent no-replay claim marker.
    outcome = consume_split_grant(
        grant_bytes=grant_bytes, verification_key=public_key,
        expected_job_id=job_id, expected_base_sha=base_sha,
        credential_file=credential_file,
        require_stop_engaged=lambda: guard("openai"),
        claimed_directory=claimed_directory, now=now)
    if outcome["state"] != "claimed_for_operator_review":
        raise PermissionError("Grant claim not confirmed")
    keys = load_provider_keys(credential_file)
    coder_instruction = (
        "Return only JSON with base_sha,branch,changes,proposal_sha256. "
        "base_sha must be " + base_sha + ". Exactly one new file "
        "tests/test_job_label.py containing a self-contained Python unittest "
        "module. Reject unsafe labels, path traversal and whitespace. No "
        "existing code changes, credentials, deployment or trading."
    )
    # Record intent BEFORE each network boundary. If transport raises, the
    # permanent claim and intent prevent any automatic or manual replay.
    _write_once(Path(checkpoint_dir) / (job_id + ".openai-attempt"), b"attempted")
    guard("openai")
    raw = transport("openai", prepare_openai_request(
        MODELS[0], coder_instruction, TASK, max_output_tokens=1024),
        keys["OPENAI_API_KEY"])
    if not isinstance(raw, bytes) or len(raw) > 1048576:
        raise PermissionError("Invalid OpenAI response")
    _write_once(Path(checkpoint_dir) / (job_id + ".openai.json"),
                _canonical({"sha256": hashlib.sha256(raw).hexdigest(),
                            "raw_hex": raw.hex(), "simulated": simulated}))
    response = openai_response(raw)
    proposal = json.loads(response.text)
    if not isinstance(proposal, dict) or set(proposal) != {"base_sha", "branch", "changes", "proposal_sha256"}:
        raise PermissionError("Invalid OpenAI proposal")
    canonical = _canonical({k: v for k, v in proposal.items() if k != "proposal_sha256"})
    digest = hashlib.sha256(canonical).hexdigest()
    proposal["proposal_sha256"] = digest
    code = json.dumps(proposal, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    plan = validate_change_plan(code, approved_base_sha=base_sha,
                                approved_proposal_sha256=digest)
    if len(plan.changes) != 1 or plan.changes[0].path != "tests/test_job_label.py":
        raise PermissionError("Proposal scope violation")
    review_payload = json.dumps({"task": TASK, "proposal": proposal, "proposal_sha256": digest},
                                sort_keys=True, separators=(",", ":"))
    if len(review_payload.encode("utf-8")) > 12000:
        raise PermissionError("Claude review input too large")
    _write_once(Path(checkpoint_dir) / (job_id + ".claude-attempt"), b"attempted")
    guard("anthropic")
    raw_review = transport("anthropic", prepare_anthropic_request(
        MODELS[1],
        "Review exact proposal_sha256 and proposed test code. Return ONLY JSON "
        "with proposal_sha256,approved,findings. Reject unsafe or invalid code.",
        review_payload, max_tokens=512, structured_review=True),
        keys["ANTHROPIC_API_KEY"])
    if not isinstance(raw_review, bytes) or len(raw_review) > 1048576:
        raise PermissionError("Invalid Claude response")
    _write_once(Path(checkpoint_dir) / (job_id + ".claude.json"),
                _canonical({"sha256": hashlib.sha256(raw_review).hexdigest(),
                            "raw_hex": raw_review.hex(), "simulated": simulated}))
    review = anthropic_response(raw_review)
    verified = validate_review(review.text, digest)
    _write_once(Path(checkpoint_dir) / (job_id + ".result.json"),
        _canonical({"job_id": job_id, "proposal_sha256": digest,
                    "state": "operator_review_required" if verified.approved else "review_rejected",
                    "approved": verified.approved, "findings": list(verified.findings),
                    "simulated": simulated, "execution_authorised": False,
                    "github_writes": 0, "docker_executed": False,
                    "billing_verified": False,
                    "openai_usage": [response.input_tokens, response.output_tokens],
                    "claude_usage": [review.input_tokens, review.output_tokens]}))
    return {"state": "operator_review_required" if verified.approved else "review_rejected",
            "job_id": job_id, "proposal_sha256": digest,
            "provider_calls": 0 if simulated else 2,
            "docker_executed": False, "github_writes": 0}
