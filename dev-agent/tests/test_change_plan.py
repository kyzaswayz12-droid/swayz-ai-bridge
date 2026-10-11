import json
import unittest
from agent.change_plan import validate_change_plan,proposal_digest

BASE="a"*40
DIGEST=proposal_digest("example proposal")

def make(path="tests/test_new.py",branch="agent/task-1",base=BASE,digest=DIGEST):
    return json.dumps({"base_sha":base,"proposal_sha256":digest,
        "branch":branch,"changes":[{"path":path,"content":"assert True\n"}]})

class ChangePlanTests(unittest.TestCase):
    def test_valid_plan(self):
        plan=validate_change_plan(make(),approved_base_sha=BASE,
                                  approved_proposal_sha256=DIGEST)
        self.assertEqual(plan.branch,"agent/task-1")
        self.assertEqual(plan.changes[0].path,"tests/test_new.py")

    def test_reject_stale_commit(self):
        with self.assertRaises(ValueError):
            validate_change_plan(make(base="b"*40),approved_base_sha=BASE,
                                 approved_proposal_sha256=DIGEST)

    def test_reject_wrong_proposal(self):
        with self.assertRaises(ValueError):
            validate_change_plan(make(digest="b"*64),approved_base_sha=BASE,
                                 approved_proposal_sha256=DIGEST)

    def test_reject_unsafe_paths(self):
        for path in ("../secret",".github/workflows/deploy.yml",
                     "config/keys.json","Dockerfile","/tmp/file","a/../../b"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    validate_change_plan(make(path=path),approved_base_sha=BASE,
                                         approved_proposal_sha256=DIGEST)

    def test_reject_unapproved_branch(self):
        with self.assertRaises(ValueError):
            validate_change_plan(make(branch="main"),approved_base_sha=BASE,
                                 approved_proposal_sha256=DIGEST)
