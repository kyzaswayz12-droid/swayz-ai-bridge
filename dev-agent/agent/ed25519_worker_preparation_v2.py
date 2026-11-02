"""Offline v2 signed worker preparation with durable journal admission.

No Docker, key provisioning or remote fetch. The caller's observed commit
must come from an independently attested trusted checkout.
"""
from .ed25519_worker_admission_v2 import admit_worker_envelope_v2
from .ed25519_worker_envelope_v2 import verify_worker_envelope_v2
from .test_handoff import prepare_test_handoff
from .staging_manifest import verify_staged_changes
from .worker_snapshot import prepare_readonly_snapshot
from .snapshot_reverification import verify_snapshot_before_execution
from .snapshot_execution_plan import plan_snapshot_execution
from .worker_journal import WorkerJournal
from pathlib import Path


def prepare_v2_worker_job(inbox, raw, signature, public_key, *,
                          job_id, workspace, changes, observed_commit,
                          image_digest, approved_images, snapshot_root, journal_path):
    root = Path(snapshot_root)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink() or root.resolve() != root:
        raise PermissionError("Invalid snapshot root")
    handoff = prepare_test_handoff(job_id, workspace, changes)
    payload = verify_worker_envelope_v2(
        raw, signature, public_key, expected_image_digest=image_digest)
    if payload["job_id"] != job_id:
        raise PermissionError("Job identity mismatch")
    manifest = verify_staged_changes(workspace, changes)
    if not isinstance(approved_images, frozenset) or image_digest not in approved_images:
        raise PermissionError("Image not approved")
    # Refuse invalid jobs before any persistent admission.
    if payload["manifest_sha256"] != handoff.manifest_sha256 or payload["commit_sha"] != observed_commit:
        raise PermissionError("Manifest or commit mismatch")
    admitted = admit_worker_envelope_v2(
        inbox, raw, signature, public_key, expected_manifest=handoff.manifest_sha256,
        expected_commit=observed_commit, expected_image_digest=image_digest,
        approved_image_digests=approved_images)
    if not admitted:
        raise PermissionError("Duplicate job")
    journal = WorkerJournal(journal_path)
    try:
        if not journal.record_admission(job_id):
            raise PermissionError("Duplicate journal job")
        try:
            hashes = {name: info["sha256"] for name, info in manifest.items()}
            snapshot = prepare_readonly_snapshot(
                workspace, root / job_id, expected_files=hashes)
            verify_snapshot_before_execution(snapshot, hashes)
            plan_snapshot_execution(
                job_id=job_id, snapshot=str(snapshot),
                snapshot_root=str(root), image_digest=image_digest)
        except BaseException:
            journal.transition(job_id, "admitted", "blocked",
                               excerpt="Snapshot preparation failed")
            raise
        return str(snapshot), hashes
    finally:
        journal.close()
