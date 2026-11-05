"""Trusted request handoff boundary for independently admitted development jobs.

The development worker never signs, reads keys or starts systemd. The
privileged signer callback must be supplied by a separate authenticated
service, and must validate the existing queue, admission and journal ledgers.
"""
import re

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SHA = re.compile(r"^[a-f0-9]{40}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def submit_to_trusted_signer(*, job_id, plan, prepared_snapshot,
                             require_running, signer_request):
    if not callable(require_running) or not callable(signer_request):
        raise PermissionError("Independent stop guard and signer required")
    if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
        raise PermissionError("Invalid job identity")
    if not isinstance(prepared_snapshot, dict) or set(prepared_snapshot) != {
            "job_id", "commit_sha", "proposal_sha256", "snapshot",
            "snapshot_root", "expected_hashes", "manifest_sha256",
            "image_digest"}:
        raise PermissionError("Untrusted snapshot metadata")
    if prepared_snapshot["job_id"] != job_id:
        raise PermissionError("Snapshot job identity mismatch")
    if (not isinstance(prepared_snapshot["commit_sha"], str)
            or not _SHA.fullmatch(prepared_snapshot["commit_sha"])
            or not isinstance(prepared_snapshot["proposal_sha256"], str)
            or not _DIGEST.fullmatch(prepared_snapshot["proposal_sha256"])
            or not isinstance(prepared_snapshot["manifest_sha256"], str)
            or not _DIGEST.fullmatch(prepared_snapshot["manifest_sha256"])):
        raise PermissionError("Invalid snapshot identity digests")
    if (getattr(plan, "base_sha", None) != prepared_snapshot["commit_sha"]
            or getattr(plan, "proposal_sha256", None)
            != prepared_snapshot["proposal_sha256"]):
        raise PermissionError("Snapshot does not match reviewed proposal")
    if not isinstance(prepared_snapshot["expected_hashes"], dict) or not prepared_snapshot["expected_hashes"]:
        raise PermissionError("Missing immutable snapshot hashes")
    if any(not isinstance(name, str) or not name or name.startswith("/")
           or ".." in name.split("/") or not isinstance(digest, str)
           or not _DIGEST.fullmatch(digest)
           for name, digest in prepared_snapshot["expected_hashes"].items()):
        raise PermissionError("Invalid immutable snapshot hashes")
    if not isinstance(prepared_snapshot["image_digest"], str) or not prepared_snapshot["image_digest"].startswith("sha256:") or not _DIGEST.fullmatch(prepared_snapshot["image_digest"][7:]):
        raise PermissionError("Unapproved image identity format")
    require_running()
    # Signer must independently verify all filesystem paths, ledger states,
    # image allowlist, and key ownership; never trust worker-supplied paths.
    receipt = signer_request(
        job_id=job_id, commit_sha=prepared_snapshot["commit_sha"],
        proposal_sha256=prepared_snapshot["proposal_sha256"],
        manifest_sha256=prepared_snapshot["manifest_sha256"])
    if not isinstance(receipt, dict) or receipt.get("state") != "admitted" or receipt.get("job_id") != job_id:
        raise PermissionError("Trusted signer did not confirm admission")
    require_running()
    return {"state": "admitted", "job_id": job_id}
