import json
import tempfile
import unittest
from pathlib import Path
from agent.proposal_checkpoint import save_proposal

class ProposalCheckpointTests(unittest.TestCase):
    def test_save_and_recover(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/"checkpoints"
            result=save_proposal(folder,"Propose safer risk controls")
            self.assertTrue(result["saved"])
            data=json.loads(Path(result["path"]).read_text())
            self.assertEqual(data["proposal"],"Propose safer risk controls")
            self.assertEqual(data["review_state"],"pending")
            self.assertEqual(Path(result["path"]).stat().st_mode & 0o777,0o600)
    def test_duplicate_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            save_proposal(folder,"Same proposal")
            self.assertFalse(save_proposal(folder,"Same proposal")["saved"])
    def test_invalid_proposal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                save_proposal(Path(d),"")
