import json
import unittest
from agent.collaboration import collaborate,offline_demo

class CollaborationTests(unittest.TestCase):
    def test_mock_review_requires_approval(self):
        result=offline_demo("Improve test coverage")
        self.assertEqual(result.state,"approval_required")
        self.assertTrue(result.approved_by_reviewer)

    def test_rejection_blocks(self):
        result=collaborate("Review code",lambda task:"candidate",
            lambda task,proposal,digest:json.dumps({
                "proposal_sha256":digest,"approved":False,
                "findings":["Insufficient test coverage"]}))
        self.assertEqual(result.state,"blocked")

    def test_mismatched_proposal_blocks(self):
        with self.assertRaisesRegex(ValueError,"fingerprint"):
            collaborate("Review code",lambda task:"candidate",
                lambda task,proposal,digest:json.dumps({
                    "proposal_sha256":"0"*64,"approved":True,"findings":[]}))

    def test_empty_task_rejected_without_calls(self):
        def forbidden(*args):
            raise AssertionError("Worker must not be called")
        with self.assertRaises(ValueError):
            collaborate(" ",forbidden,forbidden)
