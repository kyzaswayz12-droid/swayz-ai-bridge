import tempfile
import unittest
from pathlib import Path
from agent.coding_job import prepare_coding_job
from agent.test_handoff import prepare_test_handoff

class TestHandoffTests(unittest.TestCase):
    def test_verified_workspace_handoff(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"private"
            parent.mkdir(mode=0o700)
            changes={"tests/test_risk.py":"assert True"}
            job=prepare_coding_job(parent,"job1",changes)
            handoff=prepare_test_handoff("job1",Path(job.workspace),changes)
            self.assertEqual(handoff.state,"awaiting_trusted_worker")
            self.assertEqual(len(handoff.manifest_sha256),64)
    def test_workspace_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d)/"private"
            parent.mkdir(mode=0o700)
            changes={"a.py":"x"}
            job=prepare_coding_job(parent,"job1",changes)
            with self.assertRaises(ValueError):
                prepare_test_handoff("other",Path(job.workspace),changes)
