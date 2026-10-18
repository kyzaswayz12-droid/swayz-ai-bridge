"""Version 2 signed worker envelope, binding the Docker image to the job.

The legacy envelope is not accepted by this verifier. No keys are stored here.
"""
import re
from .ed25519_handoff import sign_job_ed25519, verify_job_ed25519
from .test_jobs import TestJob, serialize_job

_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
_FIELDS = frozenset({"version", "job_id", "repository", "commit_sha",
                     "suite", "manifest_sha256", "image_digest"})


def _validate(payload):
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise ValueError("Invalid v2 envelope fields")
    if payload["version"] != "2":
        raise ValueError("Invalid envelope version")
    if not isinstance(payload["image_digest"], str) or not _DIGEST.fullmatch(payload["image_digest"]):
        raise ValueError("Invalid image digest")
    if payload["image_digest"] == "sha256:" + "0" * 64:
        raise ValueError("Placeholder image digest")
    manifest = payload["manifest_sha256"]
    if not isinstance(manifest, str) or not re.fullmatch(r"[a-f0-9]{64}", manifest):
        raise ValueError("Invalid manifest digest")
    serialize_job(TestJob(payload["job_id"], payload["repository"],
                          payload["commit_sha"], payload["suite"]))
    return payload


def sign_worker_envelope_v2(payload, private_key):
    from .ed25519_handoff import canonical_job_bytes
    import json
    _validate(payload)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return raw, private_key.sign(raw)


def verify_worker_envelope_v2(raw, signature, public_key, *, expected_image_digest):
    import json
    from cryptography.exceptions import InvalidSignature
    if not isinstance(raw, bytes) or len(raw) > 4096 or not isinstance(signature, bytes) or len(signature) != 64:
        raise ValueError("Invalid envelope")
    try:
        public_key.verify(signature, raw)
    except InvalidSignature:
        raise ValueError("Invalid signature") from None
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Invalid JSON") from None
    _validate(payload)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if raw != canonical:
        raise ValueError("Noncanonical envelope")
    if payload["image_digest"] != expected_image_digest:
        raise PermissionError("Signed Docker image mismatch")
    return payload
