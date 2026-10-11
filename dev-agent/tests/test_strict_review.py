import unittest
from agent.review_validation import validate_review

class StrictReviewTests(unittest.TestCase):
    HASH="a"*64
    def test_markdown_fence_rejected(self):
        with self.assertRaisesRegex(ValueError,"Review must be JSON"):
            validate_review('''```json
{"proposal_sha256":"'''+self.HASH+'''","approved":true,"findings":[]}
```''',self.HASH)
    def test_prose_rejected(self):
        with self.assertRaisesRegex(ValueError,"Review must be JSON"):
            validate_review("Looks good, approved!",self.HASH)
    def test_wrong_hash_rejected(self):
        import json
        with self.assertRaisesRegex(ValueError,"fingerprint"):
            validate_review(json.dumps({"proposal_sha256":"b"*64,
                "approved":True,"findings":[]}),self.HASH)
