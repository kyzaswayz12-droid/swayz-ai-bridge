import unittest
from agent.providers import prepare_anthropic_request, review_json_schema

class StructuredReviewRequestTests(unittest.TestCase):
    def test_structured_review_has_json_schema(self):
        req=prepare_anthropic_request("claude-haiku-4-5-20251001","Review","proposal",max_tokens=512,structured_review=True)
        fmt=req["output_config"]["format"]
        self.assertEqual(fmt["type"],"json_schema")
        self.assertEqual(set(fmt["schema"]["required"]),{"proposal_sha256","approved","findings"})
        self.assertFalse(fmt["schema"]["additionalProperties"])
        self.assertEqual(fmt["schema"]["properties"]["approved"]["type"],"boolean")

    def test_normal_request_unchanged(self):
        req=prepare_anthropic_request("claude-haiku-4-5-20251001","Review","proposal")
        self.assertNotIn("output_config",req)

    def test_output_cap_still_enforced(self):
        with self.assertRaises(ValueError):
            prepare_anthropic_request("claude-haiku-4-5-20251001","Review","proposal",max_tokens=5000,structured_review=True)
