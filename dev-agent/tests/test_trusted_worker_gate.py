import tempfile
import unittest
from pathlib import Path
from agent.coding_job import prepare_coding_job
from agent.test_handoff import prepare_test_handoff
from agent.test_jobs import TestJob
from agent.signed_handoff import sign_manifest_job
from agent.signed_job_inbox import admit_signed_handoff
from agent.job_inbox import JobInbox
from agent.trusted_worker_gate import verify_and_admit

KEY=b"worker-test-secret-12345678901234567890"

class TrustedWorkerGateTests(unittest.TestCase):
    def test_verified_admission_and_replay(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"private"
            parent.mkdir(mode=0o700)
            changes={"tests/test_risk.py":"assert True"}
            job=prepare_coding_job(parent,"job1",changes)
            handoff=prepare_test_handoff("job1",Path(job.workspace),changes)
            envelope=TestJob("job1","kyzaswayz12-droid/swayz-ai-bridge","a"*40,"python-unittest")
            raw,sig=sign_manifest_job(envelope,handoff.manifest_sha256,KEY)
            inbox=JobInbox()
            self.assertTrue(verify_and_admit(inbox,raw,sig,KEY,job_id="job1",workspace=job.workspace,changes=changes))
            self.assertFalse(verify_and_admit(inbox,raw,sig,KEY,job_id="job1",workspace=job.workspace,changes=changes))
            inbox.close()
    def test_modified_workspace_rejected_before_admission(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"private"
            parent.mkdir(mode=0o700)
            changes={"a.py":"safe"}
            job=prepare_coding_job(parent,"job1",changes)
            handoff=prepare_test_handoff("job1",Path(job.workspace),changes)
            envelope=TestJob("job1","kyzaswayz12-droid/swayz-ai-bridge","a"*40,"python-unittest")
            raw,sig=sign_manifest_job(envelope,handoff.manifest_sha256,KEY)
            (Path(job.workspace)/"a.py").write_text("tampered")
            inbox=JobInbox()
            with self.assertRaises(ValueError):
                verify_and_admit(inbox,raw,sig,KEY,job_id="job1",workspace=job.workspace,changes=changes)
            self.assertIsNone(inbox.status("job1"))
            inbox.close()
