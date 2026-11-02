"""Single supervised signed-job workflow.

The Docker executor is disabled unless explicitly authorised. This adapter
is not a privileged daemon and does not provide unattended operation.
"""
from .attested_worker_preparation import prepare_from_attested_checkout
from .staging_manifest import verify_staged_changes
from .supervised_docker_executor import execute_supervised_job


def run_signed_supervised_job(inbox, raw, signature, secret, *,
                              job_id, checkout, workspace, changes,
                              image_digest, approved_image_digests,
                              snapshot_root, journal_path, git_runner,
                              authorised=False, executor=None):
    if authorised is not True:
        raise PermissionError("Supervised job execution disabled")
    if not isinstance(approved_image_digests, frozenset) or image_digest not in approved_image_digests:
        raise PermissionError("Unapproved image")
    manifest = verify_staged_changes(workspace, changes)
    prepared = prepare_from_attested_checkout(
        inbox, raw, signature, secret, job_id=job_id, checkout=checkout,
        workspace=workspace, changes=changes, image_digest=image_digest,
        snapshot_root=snapshot_root, journal_path=journal_path,
        git_runner=git_runner)
    if prepared.state != "awaiting_trusted_worker":
        raise PermissionError("Job not prepared")
    hashes = {name: item["sha256"] for name, item in manifest.items()}
    return execute_supervised_job(
        job_id=job_id, snapshot=prepared.snapshot, snapshot_root=snapshot_root,
        expected_hashes=hashes, image_digest=image_digest,
        approved_image_digests=approved_image_digests, journal_path=journal_path,
        authorised=True, executor=executor)
