import json
import tempfile
import unittest
from pathlib import Path
from agent.proposal_checkpoint import save_proposal
from agent.review_failure_record import save_review_failure

class ReviewFailureRecordTests(unittest.TestCase):
    def test_failure_record_preserves_proposal(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/"checkpoints"
            saved=save_proposal(folder,"A risk-control test proposal")
            target=save_review_failure(folder,saved["proposal_sha256"],"review_invalid_json")
            failure=json.loads(target.read_text())
            self.assertEqual(failure["state"],"blocked")
            self.assertEqual(failure["reason"],"review_invalid_json")
            self.assertEqual(json.loads(Path(saved["path"]).read_text())["review_state"],"pending")
            self.assertEqual(target.stat().st_mode & 0o777,0o600)
    def test_unrecognised_reason_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            saved=save_proposal(folder,"Test")
            with self.assertRaises(ValueError):
                save_review_failure(folder,saved["proposal_sha256"],"API_KEY=secret")
