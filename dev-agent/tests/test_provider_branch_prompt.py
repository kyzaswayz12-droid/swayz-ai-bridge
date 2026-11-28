"""Offline regression tests for the exact provider branch instruction.

The real one-shot returned add/job-label-validator-tests, which the existing
security validator correctly rejected. No provider calls or production files.
"""
import json
import unittest

from agent.change_plan import validate_change_plan
from agent.providers import prepare_openai_request
from agent.split_provider_authority import TASK
from agent.split_provider_transport import _coder_instruction


BASE = "a" * 40
APPROVAL = "b" * 64


def plan(branch):
    return json.dumps({
        "base_sha": BASE,
        "proposal_sha256": APPROVAL,
        "branch": branch,
        "changes": [{"path": "tests/test_job_label.py",
                     "content": "import unittest\n"}],
    })


class ProviderBranchInstructionTests(unittest.TestCase):
    def test_prompt_requires_exact_allowlisted_branch(self):
        instruction = _coder_instruction(BASE)
        self.assertIn("branch field MUST be exactly agent/job-label-validator-tests", instruction)
        self.assertIn("Do not choose a different branch name or prefix", instruction)
        self.assertIn("tests/test_job_label.py", instruction)
        request = prepare_openai_request("gpt-5-mini", instruction, TASK, max_output_tokens=3072)
        self.assertEqual(request["instructions"], instruction)
        self.assertEqual(request["reasoning"], {"effort": "low"})

    def test_actual_failed_branch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsafe development branch"):
            validate_change_plan(plan("add/job-label-validator-tests"),
                approved_base_sha=BASE, approved_proposal_sha256=APPROVAL)

    def test_exact_requested_branch_is_accepted(self):
        result = validate_change_plan(plan("agent/job-label-validator-tests"),
            approved_base_sha=BASE, approved_proposal_sha256=APPROVAL)
        self.assertEqual(result.branch, "agent/job-label-validator-tests")
        self.assertEqual(result.changes[0].path, "tests/test_job_label.py")

    def test_security_validator_remains_strict(self):
        for branch in ("main", "feature/label-validator", "agent/Unsafe", "../agent/x"):
            with self.subTest(branch=branch), self.assertRaisesRegex(ValueError, "Unsafe development branch"):
                validate_change_plan(plan(branch), approved_base_sha=BASE,
                                     approved_proposal_sha256=APPROVAL)


if __name__ == "__main__":
    unittest.main()
