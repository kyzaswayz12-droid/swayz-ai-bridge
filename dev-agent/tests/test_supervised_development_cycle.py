import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from agent.change_plan import proposal_digest
from agent.development_task_intake import provision_task_queue, DevelopmentTaskQueue
from agent.supervised_development_cycle import complete_supervised_cycle


class GitHubStub:
    swayz_draft_only = True
    def __init__(self):
        self.events = []
    def read_branch_head(self, repo, branch):
        return "a"*40
    def branch_exists(self, repo, branch):
        return False
    def create_branch(self, *args):
        self.events.append("branch")
    def put_new_file(self, *args):
        self.events.append("file")
    def create_pull_request(self, repo, **kwargs):
        self.events.append("pr")
        if not kwargs["draft"]:
            raise AssertionError("Non-draft PR")
        return {"draft": True, "number": 9}


class DevelopmentCycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = str(Path(self.temp.name) / "queue.db")
        provision_task_queue(path)
        with sqlite3.connect(path) as db:
            db.execute("INSERT INTO development_tasks VALUES(?,?,?,?)",
                       ("job1","2026-11-04","Fix smoke test","queued"))
        self.queue = DevelopmentTaskQueue(path)
        self.github = GitHubStub()
        self.plan = json.dumps(dict(
            base_sha="a"*40, proposal_sha256="b"*64,
            branch="agent/cycle-smoke",
            changes=[dict(path="tests/smoke.py", content="assert True\n")]))
        self.review = json.dumps(dict(
            proposal_sha256="b"*64, approved=True, findings=[]))
        self.test_calls = 0

    def runner(self, **kwargs):
        self.test_calls += 1
        return {"state":"passed", "cleanup_verified":True}

    def cycle(self, **overrides):
        args = dict(job_id="job1", task_queue=self.queue,
                    require_running=lambda: None,
                    approved_base_sha="a"*40,
                    approved_proposal_sha256="b"*64,
                    base_branch="main", coding_response=self.plan,
                    review_response=self.review,
                    run_verified_tests=self.runner, github=self.github)
        args.update(overrides)
        return complete_supervised_cycle(**args)

    def test_complete_cycle(self):
        result = self.cycle()
        self.assertEqual(result.state, "done")
        self.assertEqual(self.queue.get("job1")["state"], "done")
        self.assertEqual(self.github.events, ["branch", "file", "pr"])
        self.assertEqual(self.test_calls, 1)

    def test_unapproved_review_blocks_before_execution(self):
        with self.assertRaises(PermissionError):
            self.cycle(review_response=json.dumps(dict(
                proposal_sha256="b"*64, approved=False, findings=[])))
        self.assertEqual(self.test_calls, 0)
        self.assertEqual(self.queue.get("job1")["state"], "queued")

    def test_failed_docker_cleanup_prevents_pr(self):
        result = self.cycle(run_verified_tests=lambda **kwargs: {
            "state":"passed", "cleanup_verified":False})
        self.assertEqual(result.state, "blocked")
        self.assertEqual(self.github.events, [])

    def test_stop_prevents_job_claim(self):
        def stopped():
            raise PermissionError("Stopped")
        with self.assertRaises(PermissionError):
            self.cycle(require_running=stopped)
        self.assertEqual(self.queue.get("job1")["state"], "queued")

    def test_duplicate_completion_rejected(self):
        self.cycle()
        with self.assertRaises(PermissionError):
            self.cycle()
        self.assertEqual(self.github.events, ["branch", "file", "pr"])
