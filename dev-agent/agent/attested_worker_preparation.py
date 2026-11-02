"""Offline trusted-checkout gate for signed worker preparation.

The Git runner must be supplied by a separate trusted service. This does not
execute Docker or establish that staged changes originate from the checkout.
"""
from .signed_handoff import verify_manifest_job
from .test_handoff import prepare_test_handoff
from .git_checkout_attestation import attest_git_checkout
from .integrated_worker_preparation import prepare_integrated_job


def prepare_from_attested_checkout(inbox, raw, signature, secret, *,
                                   job_id, checkout, workspace, changes,
                                   image_digest, snapshot_root, journal_path,
                                   git_runner):
    # Authenticate envelope and staged manifest before any durable admission.
    handoff = prepare_test_handoff(job_id, workspace, changes)
    job = verify_manifest_job(raw, signature, secret, handoff.manifest_sha256)
    if job.job_id != job_id:
        raise PermissionError("Signed job ID mismatch")
    # Never take the observed SHA from the coordinator. Obtain it from Git.
    observed = attest_git_checkout(checkout, job.commit_sha, runner=git_runner)
    return prepare_integrated_job(
        inbox, raw, signature, secret, job_id=job_id, workspace=workspace,
        changes=changes, image_digest=image_digest, snapshot_root=snapshot_root,
        journal_path=journal_path, observed_commit_sha=observed)
