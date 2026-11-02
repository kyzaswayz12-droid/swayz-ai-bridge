"""Ed25519 v2 end-to-end supervised worker adapter.

Not a daemon. No key loading, Git fetching or privilege escalation.
The caller must independently attest the checkout and approve execution.
"""
from .ed25519_worker_preparation_v2 import prepare_v2_worker_job
from .supervised_docker_executor import execute_supervised_job


def execute_v2_supervised_job(inbox, raw, signature, public_key, *,
                              job_id, workspace, changes, observed_commit,
                              image_digest, approved_images, snapshot_root,
                              journal_path, authorised=False, executor=None):
    if authorised is not True:
        raise PermissionError("Supervised v2 execution disabled")
    snapshot, hashes = prepare_v2_worker_job(
        inbox, raw, signature, public_key,
        job_id=job_id, workspace=workspace, changes=changes,
        observed_commit=observed_commit, image_digest=image_digest,
        approved_images=approved_images, snapshot_root=snapshot_root,
        journal_path=journal_path)
    return execute_supervised_job(
        job_id=job_id, snapshot=snapshot, snapshot_root=snapshot_root,
        expected_hashes=hashes, image_digest=image_digest,
        approved_image_digests=approved_images, journal_path=journal_path,
        authorised=True, executor=executor)
