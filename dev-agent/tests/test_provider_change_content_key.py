"""Regression for the third one-shot response: contents != content.

Offline only. The security validator remains strict and no provider requests
or production job mutations occur.
"""
import json
import unittest

from agent.change_plan import validate_change_plan
from agent.providers import prepare_openai_request
from agent.split_provider_authority import TASK
from agent.split_provider_transport import _coder_instruction

BASE = "a" * 40
DIGEST = "b" * 64
PATH = "tests/test_job_label.py"


def proposal(change):
    return json.dumps({
        "base_sha": BASE,
        "branch": "agent/job-label-validator-tests",
        "changes": [change],
        "proposal_sha256": DIGEST,
    })


class ProviderChangeContentKeyTests(unittest.TestCase):
    def test_coder_instruction_specifies_exact_keys(self):
        prompt = _coder_instruction(BASE)
        self.assertIn("exactly two keys: path and content", prompt)
        self.assertIn("NEVER contents", prompt)
        self.assertIn('"path":"tests/test_job_label.py","content":', prompt)
        request = prepare_openai_request("gpt-5-mini", prompt, TASK,
                                          max_output_tokens=3072)
        self.assertEqual(request["instructions"], prompt)
        self.assertEqual(request["reasoning"], {"effort": "low"})

    def test_observed_contents_alias_still_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Invalid change schema"):
            validate_change_plan(proposal({"path": PATH, "contents": "import unittest"}),
                                 approved_base_sha=BASE,
                                 approved_proposal_sha256=DIGEST)

    def test_exact_content_key_passes_existing_validator(self):
        result = validate_change_plan(proposal({"path": PATH, "content": "import unittest"}),
                                      approved_base_sha=BASE,
                                      approved_proposal_sha256=DIGEST)
        self.assertEqual(result.branch, "agent/job-label-validator-tests")
        self.assertEqual(result.changes[0].content, "import unittest")

    def test_extra_key_remains_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid change schema"):
            validate_change_plan(proposal({"path": PATH, "content": "x", "contents": "y"}),
                                 approved_base_sha=BASE,
                                 approved_proposal_sha256=DIGEST)


if __name__ == "__main__":
    unittest.main()
