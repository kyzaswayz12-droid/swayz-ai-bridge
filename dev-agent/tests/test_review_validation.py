import json
import unittest
from agent.review_validation import validate_review

SHA="a"*64

class ReviewValidationTests(unittest.TestCase):
    def test_valid_review(self):
        result=validate_review(json.dumps({"proposal_sha256":SHA,"approved":False,
            "findings":["Missing regression test"]}),SHA)
        self.assertFalse(result.approved)

    def test_wrong_fingerprint_rejected(self):
        with self.assertRaisesRegex(ValueError,"fingerprint"):
            validate_review(json.dumps({"proposal_sha256":"b"*64,"approved":True,
                "findings":[]}),SHA)

    def test_string_approval_rejected(self):
        with self.assertRaises(ValueError):
            validate_review(json.dumps({"proposal_sha256":SHA,"approved":"true",
                "findings":[]}),SHA)

    def test_unstructured_response_rejected(self):
        with self.assertRaises(ValueError):
            validate_review("Looks good",SHA)
