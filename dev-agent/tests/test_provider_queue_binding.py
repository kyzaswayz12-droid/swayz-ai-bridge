import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agent.provider_queue_binding import run_next_provider_cycle

class Queue:
    def __init__(self):
        self.state = "queued"
    def get(self, job):
        return {"task":"Fix a test","state":self.state}

class GitHub:
    swayz_draft_only = True

class ProviderQueueBindingTests(unittest.TestCase):
    def setUp(self):
        self.queue=Queue()
        self.calls=[]
        self.args=dict(queue_db="/queue",job_db="/jobs",control_db="/stop",
            task_queue=self.queue,require_running=lambda:None,
            run_verified_tests=lambda **kw:{"state":"passed","cleanup_verified":True},
            github=GitHub(),owner_approved=True,paid_calls_enabled=True,
            budget_db="/budget",fx_approval_path="/fx",now=None,
            base_branch="main",base_sha="a"*40,
            openai_model="test",anthropic_model="test",
            openai_key="dummy",anthropic_key="dummy",
            openai_maximum_usd=None,anthropic_maximum_usd=None)

    def invoke(self, cycle, **changes):
        args=dict(self.args)
        args.update(changes)
        with patch("agent.authorised_queue_cycle.select_for_provider_review",
                   return_value={"state":"queued_for_review","job_id":"job1","task":"Fix a test"}):
            return run_next_provider_cycle(cycle=cycle,**args)

    def test_existing_provider_cycle_can_deliver_draft(self):
        def cycle(**kwargs):
            self.calls.append(kwargs)
            self.queue.state="done"
            return SimpleNamespace(job_id="job1",state="done",draft_pr={"draft":True})
        self.assertEqual(self.invoke(cycle)["state"],"done")
        self.assertEqual(self.calls[0]["job_db"],"/jobs")
        self.assertIs(self.calls[0]["run_verified_tests"],self.args["run_verified_tests"])

    def test_blocked_cycle_has_no_draft(self):
        def cycle(**kwargs):
            self.queue.state="blocked"
            return SimpleNamespace(job_id="job1",state="blocked",draft_pr=None)
        self.assertEqual(self.invoke(cycle)["state"],"blocked")

    def test_paid_gate_fails_before_dispatch(self):
        def forbidden(**kwargs):
            raise AssertionError("Must not dispatch")
        with self.assertRaises(PermissionError):
            self.invoke(forbidden,paid_calls_enabled=False)

    def test_untrusted_github_rejected(self):
        with self.assertRaises(PermissionError):
            self.invoke(lambda **kw:None,github=object())

    def test_untrusted_transport_rejected(self):
        with self.assertRaises(PermissionError):
            self.invoke(lambda **kw:None,transport=object())

    def test_missing_trusted_runner_rejected(self):
        with self.assertRaises(PermissionError):
            self.invoke(lambda **kw:None,run_verified_tests=None)
