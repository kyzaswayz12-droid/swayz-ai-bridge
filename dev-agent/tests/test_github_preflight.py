import unittest
from agent.change_plan import ApprovedPlan,Change
from agent.github_preflight import prepare_draft_pr

PLAN=ApprovedPlan("a"*40,"b"*64,"agent/safe-1",(Change("tests/new.py","assert True"),))
REPO="kyzaswayz12-droid/swayz-ai-bridge"

class GitHubPreflightTests(unittest.TestCase):
    def test_valid_draft_plan(self):
        result=prepare_draft_pr(PLAN,repository=REPO,base_branch="main",
            read_branch_head=lambda repo,branch:"a"*40,
            branch_exists=lambda repo,branch:False)
        self.assertEqual(result.head_branch,"agent/safe-1")

    def test_changed_base_rejected(self):
        with self.assertRaisesRegex(ValueError,"changed"):
            prepare_draft_pr(PLAN,repository=REPO,base_branch="main",
                read_branch_head=lambda repo,branch:"c"*40,
                branch_exists=lambda repo,branch:False)

    def test_existing_branch_rejected(self):
        with self.assertRaisesRegex(ValueError,"already exists"):
            prepare_draft_pr(PLAN,repository=REPO,base_branch="main",
                read_branch_head=lambda repo,branch:"a"*40,
                branch_exists=lambda repo,branch:True)
