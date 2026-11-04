import unittest
from agent.github_draft_adapter import DraftOnlyGitHub


class GitHubDraftAdapterTests(unittest.TestCase):
    def setUp(self):
        self.api = DraftOnlyGitHub("fake-local-token")
        self.calls = []
        def fake(method, suffix, data=None):
            self.calls.append((method, suffix, data))
            if suffix.startswith("/git/ref/heads/"):
                return {"object":{"sha":"a"*40}}
            if suffix == "/pulls":
                return {"draft":True,"number":7}
            return {}
        self.api._call = fake

    def test_draft_only(self):
        pr = self.api.create_pull_request(
            "kyzaswayz12-droid/swayz-ai-bridge", base_branch="main",
            head_branch="agent/test", title="Swayz proposal", body="Review",
            draft=True)
        self.assertTrue(pr["draft"])
        self.assertEqual(self.calls[-1][2]["draft"], True)

    def test_non_draft_refused(self):
        with self.assertRaises(PermissionError):
            self.api.create_pull_request(
                "kyzaswayz12-droid/swayz-ai-bridge", base_branch="main",
                head_branch="agent/test", title="Swayz proposal", body="Review",
                draft=False)
        self.assertEqual(self.calls, [])

    def test_other_repository_refused(self):
        with self.assertRaises(PermissionError):
            self.api.create_branch("other/repo", "agent/test", "a"*40)

    def test_protected_file_refused(self):
        with self.assertRaises((ValueError, PermissionError)):
            self.api.put_new_file("kyzaswayz12-droid/swayz-ai-bridge",
                                  "agent/test", ".github/workflows/test.yml", "bad")
        self.assertEqual(self.calls, [])

    def test_new_file_committed_to_agent_branch(self):
        self.api.put_new_file("kyzaswayz12-droid/swayz-ai-bridge",
                              "agent/test", "tests/smoke.py", "assert True")
        self.assertEqual(self.calls[-1][0], "PUT")
        self.assertEqual(self.calls[-1][2]["branch"], "agent/test")
