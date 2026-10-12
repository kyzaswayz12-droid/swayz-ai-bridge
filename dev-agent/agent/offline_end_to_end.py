"""Offline end-to-end demonstration; no Docker or external calls."""
import tempfile
from pathlib import Path
from .coding_job import prepare_coding_job
from .test_handoff import prepare_test_handoff
from .test_jobs import TestJob
from .signed_handoff import sign_manifest_job
from .signed_job_inbox import admit_signed_handoff
from .job_inbox import JobInbox

def run_demo():
    with tempfile.TemporaryDirectory() as d:
        parent=Path(d)/"private"
        parent.mkdir(mode=0o700)
        changes={"tests/test_risk_limits.py":"def test_risk_limit():\n    assert 2 == 2\n"}
        staged=prepare_coding_job(parent,"demo-job-001",changes)
        handoff=prepare_test_handoff(staged.job_id,Path(staged.workspace),changes)
        job=TestJob(staged.job_id,"kyzaswayz12-droid/swayz-ai-bridge","a"*40,"python-unittest")
        secret=b"offline-demo-key-not-for-production-123"
        raw,sig=sign_manifest_job(job,handoff.manifest_sha256,secret)
        inbox=JobInbox(str(Path(d)/"inbox.db"))
        try:
            accepted=admit_signed_handoff(inbox,raw,sig,secret,handoff.manifest_sha256)
            duplicate=admit_signed_handoff(inbox,raw,sig,secret,handoff.manifest_sha256)
        finally:
            inbox.close()
        return {"state":"handoff_verified","staged_files":len(staged.manifest),
                "manifest_sha256":handoff.manifest_sha256,
                "accepted":accepted,"duplicate_accepted":duplicate,
                "docker_executed":False,"provider_calls":0,"github_writes":0}
