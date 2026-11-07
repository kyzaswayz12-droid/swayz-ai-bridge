"""Offline autonomy acceptance regressions: stop and failure boundaries.

No paid providers, real Docker, GitHub network writes, or deployment.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent.development_task_intake import DevelopmentTaskQueue
from agent.offline_queue_coordinator import select_for_provider_review
from agent.supervised_development_cycle import complete_supervised_cycle


class DraftAdapter:
    swayz_draft_only = True
    def __init__(self):
        self.writes = 0
    def read_branch_head(self, repo, branch):
        return "a" * 40
    def branch_exists(self, repo, branch):
        return False
    def create_branch(self, *args):
        self.writes += 1
    def put_new_file(self, *args):
        self.writes += 1
    def create_pull_request(self, *args, **kwargs):
        assert kwargs["draft"] is True
        self.writes += 1
        return {"draft": True}


class OfflineAutonomyFailureBoundaries(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.q, self.j, self.s = [str(root / n) for n in ("q.db", "j.db", "s.db")]
        with sqlite3.connect(self.q) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT PRIMARY KEY,day_utc TEXT,task TEXT,state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES('job1','2026-11-04','Fix test','queued')")
        with sqlite3.connect(self.j) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT PRIMARY KEY,day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES('job1','2026-11-04')")
        with sqlite3.connect(self.s) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")
        self.github = DraftAdapter()

    def stop(self):
        with sqlite3.connect(self.s) as db:
            db.execute("UPDATE agent_control SET stopped=1")

    def require_running(self):
        with sqlite3.connect(self.s) as db:
            if db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchone() != (0,):
                raise PermissionError("Stopped")

    def execute_cycle(self, runner):
        self.assertEqual(select_for_provider_review(queue_db=self.q, job_db=self.j,
                                                    control_db=self.s)["state"], "queued_for_review")
        return complete_supervised_cycle(
            job_id="job1", task_queue=DevelopmentTaskQueue(self.q),
            require_running=self.require_running,
            approved_base_sha="a"*40, approved_proposal_sha256="b"*64,
            base_branch="main",
            coding_response=json.dumps({"base_sha":"a"*40,"proposal_sha256":"b"*64,
                "branch":"agent/failure-boundary",
                "changes":[{"path":"tests/check.py","content":"assert True"}]}),
            review_response=json.dumps({"proposal_sha256":"b"*64,
                                        "approved":True,"findings":[]}),
            run_verified_tests=runner, github=self.github)

    def test_failed_tests_block_draft(self):
        result = self.execute_cycle(lambda **kwargs: {"state":"failed","cleanup_verified":True})
        self.assertEqual(result.state, "blocked")
        self.assertEqual(self.github.writes, 0)
        self.assertEqual(DevelopmentTaskQueue(self.q).get("job1")["state"], "blocked")

    def test_stop_after_tests_blocks_github(self):
        def runner(**kwargs):
            self.stop()
            return {"state":"passed","cleanup_verified":True}
        with self.assertRaises(PermissionError):
            self.execute_cycle(runner)
        self.assertEqual(self.github.writes, 0)
        self.assertEqual(DevelopmentTaskQueue(self.q).get("job1")["state"], "blocked")

    def test_test_runner_exception_blocks_job(self):
        def runner(**kwargs):
            raise RuntimeError("Runner failed")
        with self.assertRaises(RuntimeError):
            self.execute_cycle(runner)
        self.assertEqual(self.github.writes, 0)
        self.assertEqual(DevelopmentTaskQueue(self.q).get("job1")["state"], "blocked")
