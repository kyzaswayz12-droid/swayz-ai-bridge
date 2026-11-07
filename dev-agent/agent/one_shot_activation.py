"""One-shot operator-supervised signed preparation and restricted dispatch.

This joins existing, independently checked components. It is not a scheduler,
Slack endpoint, autonomous signer or deployment mechanism. No retries.
"""
import os
from pathlib import Path
from .operator_signed_request import prepare_offline_executor_request
from .restricted_dispatch import dispatch_prepared_offline_job

def run_one_supervised_handoff(*, job_id, commit_sha, manifest_sha256,
        snapshot, snapshot_root, expected_hashes, image_digest, approved_images,
        queue_db, job_db, journal_db, stop_db, signing_key_file,
        request_directory, now=None):
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    if Path(request_directory) != Path("/var/lib/swayz-executor/requests"):
        raise PermissionError("Protected executor inbox required")
    request_path = prepare_offline_executor_request(
        job_id=job_id, commit_sha=commit_sha, manifest_sha256=manifest_sha256,
        snapshot=snapshot, snapshot_root=snapshot_root,
        expected_hashes=expected_hashes, image_digest=image_digest,
        approved_images=approved_images, queue_db=queue_db, job_db=job_db,
        journal_db=journal_db, stop_db=stop_db,
        signing_key_file=signing_key_file,
        request_directory=request_directory, now=now)
    if Path(request_path) != Path(request_directory) / (job_id + ".json"):
        raise PermissionError("Unexpected prepared request")
    # Fail closed on any exception. Never remove the signed request and
    # silently retry: an operator must reconcile the journal first.
    return dispatch_prepared_offline_job(
        job_id=job_id, snapshot=snapshot, snapshot_root=snapshot_root,
        expected_hashes=expected_hashes, signing_key_path=signing_key_file,
        stop_db=stop_db)
