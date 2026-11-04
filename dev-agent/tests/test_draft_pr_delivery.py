import json
import unittest
from agent.draft_pr_delivery import deliver_approved_draft

class FakeGitHub:
    swayz_draft_only = True
    def __init__(self):
        self.events = []
    def read_branch_head(self, repo, branch):
        return "a" * 40
    def branch_exists(self, repo, branch):
        return False
    def create_branch(self, repo, branch, sha):
        self.events.append("branch")
    def put_new_file(self, repo, branch, path, content):
        self.events.append("file")
    def create_pull_request(self, repo, **kwargs):
        self.events.append("pr")
        assert kwargs["draft"] is True
        return {"draft": True, "number": 123}

class DraftDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.github = FakeGitHub()
        self.raw = json.dumps(dict(base_sha="a"*40, proposal_sha256="b"*64,
            branch="agent/delivery-smoke",
            changes=[dict(path="tests/delivery_smoke.py", content="assert True\n")]))
    def run_delivery(self, **kwargs):
        args = dict(raw_plan=self.raw, approved_base_sha="a"*40,
                    approved_proposal_sha256="b"*64, base_branch="main",
                    github=self.github, require_running=lambda: None)
        args.update(kwargs)
        return deliver_approved_draft(**args)
    def test_creates_draft_only(self):
        self.assertTrue(self.run_delivery()["draft"])
        self.assertEqual(self.github.events, ["branch", "file", "pr"])
    def test_stopped_before_branch(self):
        def stopped():
            raise PermissionError("stop")
        with self.assertRaises(PermissionError):
            self.run_delivery(require_running=stopped)
        self.assertEqual(self.github.events, [])
    def test_stopped_after_branch_prevents_file_and_pr(self):
        calls = 0
        def stop_after_first_write():
            nonlocal calls
            calls += 1
            if calls == 3:
                raise PermissionError("stop")
        with self.assertRaises(PermissionError):
            self.run_delivery(require_running=stop_after_first_write)
        self.assertEqual(self.github.events, ["branch"])
    def test_untrusted_adapter_rejected(self):
        self.github.swayz_draft_only = False
        with self.assertRaises(PermissionError):
            self.run_delivery()
        self.assertEqual(self.github.events, [])
    def test_changed_base_rejected(self):
        self.github.read_branch_head = lambda repo, branch: "c"*40
        with self.assertRaises(ValueError):
            self.run_delivery()
        self.assertEqual(self.github.events, [])
    def test_unsafe_file_rejected(self):
        doc = json.loads(self.raw)
        doc["changes"][0]["path"] = ".github/workflows/unsafe.yml"
        with self.assertRaises(ValueError):
            self.run_delivery(raw_plan=json.dumps(doc))
        self.assertEqual(self.github.events, [])
    def test_non_draft_result_rejected(self):
        self.github.create_pull_request = lambda repo, **kw: {"draft": False}
        with self.assertRaises(PermissionError):
            self.run_delivery()
