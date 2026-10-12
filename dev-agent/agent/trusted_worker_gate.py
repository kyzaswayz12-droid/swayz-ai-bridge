"""Independent manifest verification before durable signed-job admission.

Offline only. No Docker, network, or code execution.
"""
from pathlib import Path
from .test_handoff import prepare_test_handoff
from .signed_job_inbox import admit_signed_handoff

def verify_and_admit(inbox, raw, signature, secret, *, job_id, workspace, changes):
    handoff=prepare_test_handoff(job_id,Path(workspace),changes)
    return admit_signed_handoff(inbox,raw,signature,secret,handoff.manifest_sha256)
