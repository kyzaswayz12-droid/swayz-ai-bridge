"""Offline provider-to-draft integration: mocked paid transport and Docker.

Exercises the real provider-backed coordinator, durable task queue and
restricted draft delivery without external requests or execution.
"""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent.development_task_intake import DevelopmentTaskQueue
from agent.provider_backed_development_cycle import run_provider_backed_cycle
from agent.providers import ModelResponse


class DraftStub:
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
            raise AssertionError("Draft-only boundary")
        self.events.append("draft")
        return {"draft": True, "number": 1}


class ProviderToDraftTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.queue_path = str(root / "queue.db")
        self.stop_path = str(root / "stop.db")
        with sqlite3.connect(self.queue_path) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT PRIMARY KEY,day_utc TEXT,task TEXT,state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES('job1','2026-11-04','Repair test','queued')")
        with sqlite3.connect(self.stop_path) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")
        self.queue = DevelopmentTaskQueue(self.queue_path)
        self.github = DraftStub()
        self.runner_calls = 0

    def running(self):
        with sqlite3.connect(self.stop_path) as db:
            if db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchone() != (0,):
                raise PermissionError("Stopped")

    def runner(self, **kwargs):
        self.runner_calls += 1
        return {"state": "passed", "cleanup_verified": True}

    def invoke(self, **overrides):
        args = dict(job_id="job1", task_queue=self.queue, require_running=self.running,
            job_db="/unused/jobs", budget_db="/unused/budget", control_db=self.stop_path,
            fx_approval_path="/unused/fx", now=datetime(2026,11,4,tzinfo=timezone.utc),
            base_branch="main", base_sha="a"*40, openai_model="test-model",
            anthropic_model="test-model", openai_key="dummy", anthropic_key="dummy",
            openai_maximum_usd=Decimal("0.01"), anthropic_maximum_usd=Decimal("0.01"),
            run_verified_tests=self.runner, github=self.github,
            owner_approved=True, paid_calls_enabled=True)
        args.update(overrides)
        return run_provider_backed_cycle(**args)

    @staticmethod
    def fake_dispatch(**kwargs):
        if kwargs["provider"] == "openai":
            proposal = {"base_sha":"a"*40, "branch":"agent/offline-review",
                "changes":[{"path":"tests/repair.py","content":"assert True"}],
                "proposal_sha256":"0"*64}
            return SimpleNamespace(response=ModelResponse(json.dumps(proposal),1,1))
        proposal = json.loads(kwargs["task"])
        return SimpleNamespace(response=ModelResponse(json.dumps({
            "proposal_sha256":proposal["proposal_sha256"],
            "approved":True,"findings":[]}),1,1))

    @patch("agent.provider_backed_development_cycle.dispatch_reserved_provider_once")
    def test_mocked_providers_to_draft(self, dispatch):
        dispatch.side_effect = self.fake_dispatch
        result = self.invoke()
        self.assertEqual(result.state, "done")
        self.assertEqual(self.runner_calls, 1)
        self.assertEqual(self.github.events, ["branch","file","draft"])
        self.assertEqual(self.queue.get("job1")["state"], "done")
        self.assertEqual(dispatch.call_count, 2)

    @patch("agent.provider_backed_development_cycle.dispatch_reserved_provider_once")
    def test_stop_after_coding_prevents_review(self, dispatch):
        def coding_then_stop(**kwargs):
            result = self.fake_dispatch(**kwargs)
            with sqlite3.connect(self.stop_path) as db:
                db.execute("UPDATE agent_control SET stopped=1")
            return result
        dispatch.side_effect = coding_then_stop
        with self.assertRaises(PermissionError):
            self.invoke()
        self.assertEqual(dispatch.call_count, 1)
        self.assertEqual(self.runner_calls, 0)
        self.assertEqual(self.github.events, [])
        self.assertEqual(self.queue.get("job1")["state"], "queued")

    @patch("agent.provider_backed_development_cycle.dispatch_reserved_provider_once")
    def test_disabled_paid_gate_prevents_dispatch(self, dispatch):
        with self.assertRaises(PermissionError):
            self.invoke(paid_calls_enabled=False)
        dispatch.assert_not_called()
        self.assertEqual(self.queue.get("job1")["state"], "queued")
