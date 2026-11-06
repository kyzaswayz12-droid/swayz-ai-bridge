"""Privileged signer receiving boundary for Swayz development jobs.

Only a separately authenticated root-owned service may call this function.
The untrusted AI worker provides job identity, never paths, keys, ledger
locations, approved images or an arbitrary execution callback.
This module prepares an immutable request; it does not start execution.
"""
import os
import re
from .operator_signed_request import prepare_offline_executor_request

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SHA = re.compile(r"^[a-f0-9]{40}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def receive_authorised_signing_request(*, identity, load_trusted_job,
                                       require_running,
                                       prepare=prepare_offline_executor_request):
    if os.geteuid() != 0:
        raise PermissionError("Root-owned signing service required")
    if not callable(load_trusted_job) or not callable(require_running):
        raise PermissionError("Trusted job loader and stop guard required")
    if not isinstance(identity, dict) or set(identity) != {
            "job_id", "commit_sha", "proposal_sha256", "manifest_sha256"}:
        raise PermissionError("Invalid signing identity")
    job_id, commit, proposal, manifest = (
        identity["job_id"], identity["commit_sha"],
        identity["proposal_sha256"], identity["manifest_sha256"])
    if (not isinstance(job_id, str) or not _ID.fullmatch(job_id)
            or not isinstance(commit, str) or not _SHA.fullmatch(commit)
            or not isinstance(proposal, str) or not _DIGEST.fullmatch(proposal)
            or not isinstance(manifest, str) or not _DIGEST.fullmatch(manifest)):
        raise PermissionError("Invalid signing identity values")
    require_running()
    # The trusted loader must obtain the snapshot and policy from protected
    # state, never from worker-supplied paths or metadata.
    trusted = load_trusted_job(job_id=job_id)
    required = {"job_id", "commit_sha", "proposal_sha256", "manifest_sha256",
                "snapshot", "snapshot_root", "expected_hashes", "image_digest",
                "approved_images", "queue_db", "job_db", "journal_db",
                "stop_db", "signing_key_file", "request_directory"}
    if not isinstance(trusted, dict) or set(trusted) != required:
        raise PermissionError("Trusted job metadata incomplete")
    if any(trusted[k] != identity[k] for k in identity):
        raise PermissionError("Trusted admission identity mismatch")
    require_running()
    # The existing root-only signer re-verifies stop, immutable snapshot,
    # approved image, claimed queue, daily admission, journal and key modes.
    request_path = prepare(**{k: v for k, v in trusted.items()
                              if k != "proposal_sha256"})
    if not isinstance(request_path, str) or not request_path:
        raise PermissionError("Trusted signer returned no request")
    require_running()
    return {"state": "admitted", "job_id": job_id}
