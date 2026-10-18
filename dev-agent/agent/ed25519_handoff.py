"""Ed25519 signatures for canonical Swayz job envelopes.

This module does not load or generate production keys. The trusted signer
must keep its private key outside the AI-controlled repository and process.
"""
import json
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

FIELDS = frozenset({"job_id", "repository", "commit_sha", "suite", "manifest_sha256"})


def canonical_job_bytes(payload):
    if not isinstance(payload, dict) or set(payload) != FIELDS:
        raise ValueError("Invalid signed-job schema")
    if not all(isinstance(value, str) and value for value in payload.values()):
        raise ValueError("Invalid signed-job values")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def sign_job_ed25519(payload, private_key):
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("Ed25519 private key required")
    raw = canonical_job_bytes(payload)
    return raw, private_key.sign(raw)


def verify_job_ed25519(raw, signature, public_key):
    if not isinstance(public_key, Ed25519PublicKey):
        raise TypeError("Ed25519 public key required")
    if not isinstance(raw, bytes) or not isinstance(signature, bytes) or len(signature) != 64:
        raise ValueError("Invalid signature envelope")
    try:
        public_key.verify(signature, raw)
    except InvalidSignature:
        raise ValueError("Invalid signature") from None
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Invalid job JSON") from None
    if canonical_job_bytes(payload) != raw:
        raise ValueError("Noncanonical signed job")
    return payload
