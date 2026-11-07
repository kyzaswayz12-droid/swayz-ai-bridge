"""Offline integration: selected queue item through supervised cycle.

All provider outputs and Docker/GitHub interfaces are test doubles.
No paid requests, Docker execution, GitHub writes or unattended scheduling.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent.development_task_intake import DevelopmentTaskQueue
from agent.offline_queue_coordinator import select_for_provider_review
from agent.supervised_development_cycle import complete_supervised_cycle


class DraftOnlyGitHub:
    swayz_draft_only = True
    def __init__(self):
        self.events = []
    def read_branch_head(self, repo, branch):
        return "a" * 40
    def branch_exists(self, repo, branch):
        return False
    def create_branch(self, *args):
        self.events.append("branch")
    def put_new_file(self, *args):
        self.events.append("file")
    def create_pull_request(self, *args, **kwargs):
        if kwargs.get("draft") is not True:
            raise AssertionError("Draft required")
        self.events.append("draft")
        return {"draft": True, "number": 1}


class ReviewToDraftIntegrationTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.queue, self.jobs, self.stop = [str(root / n) for n in ("queue.db", "jobs.db", "stop.db")]
        with sqlite3.connect(self.queue) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT PRIMARY KEY,day_utc TEXT,task TEXT,state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES('job1','2026-11-04','Fix tests','queued')")
        with sqlite3.connect(self.jobs) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT PRIMARY KEY,day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES('job1','2026-11-04')")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")
        self.github = DraftOnlyGitHub()
        self.test_calls = 0

    def running(self):
        with sqlite3.connect(self.stop) as db:
            if db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchone() != (0,):
                raise PermissionError("Emergency stop")

    def select(self):
        return select_for_provider_review(queue_db=self.queue, job_db=self.jobs, control_db=self.stop)

    def run_tests(self, **kwargs):
        self.test_calls += 1
        return {"state": "passed", "cleanup_verified": True}

    def cycle(self, review_approved=True, runner=None):
        coding = json.dumps({"base_sha": "a"*40, "proposal_sha256": "b"*64,
                             "branch": "agent/offline-integration",
                             "changes": [{"path": "tests/fix.py", "content": "assert True"}]})
        review = json.dumps({"proposal_sha256": "b"*64,
                             "approved": review_approved, "findings": []})
        return complete_supervised_cycle(
            job_id="job1", task_queue=DevelopmentTaskQueue(self.queue),
            require_running=self.running, approved_base_sha="a"*40,
            approved_proposal_sha256="b"*64, base_branch="main",
            coding_response=coding, review_response=review,
            run_verified_tests=runner or self.run_tests, github=self.github)

    def test_selection_review_test_and_draft_delivery(self):
        self.assertEqual(self.select()["state"], "queued_for_review")
        self.assertEqual(self.cycle().state, "done")
        self.assertEqual(self.test_calls, 1)
        self.assertEqual(self.github.events, ["branch", "file", "draft"])
        self.assertEqual(DevelopmentTaskQueue(self.queue).get("job1")["state"], "done")

    def test_rejected_review_never_claims_or_tests(self):
        self.select()
        with self.assertRaises(PermissionError):
            self.cycle(review_approved=False)
        self.assertEqual(self.test_calls, 0)
        self.assertEqual(DevelopmentTaskQueue(self.queue).get("job1")["state"], "queued")

    def test_failed_cleanup_never_delivers(self):
        self.select()
        result = self.cycle(runner=lambda **kw: {"state": "passed", "cleanup_verified": False})
        self.assertEqual(result.state, "blocked")
        self.assertEqual(self.github.events, [])

    def test_emergency_stop_before_selection(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=1")
        with self.assertRaises(PermissionError):
            self.select()
        self.assertEqual(self.github.events, [])

    def test_second_cycle_does_not_repeat_delivery(self):
        self.select()
        self.cycle()
        with self.assertRaises(PermissionError):
            self.cycle()
        self.assertEqual(self.github.events.count("draft"), 1)
