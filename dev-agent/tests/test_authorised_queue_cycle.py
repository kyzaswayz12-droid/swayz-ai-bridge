import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agent.authorised_queue_cycle import run_next_authorised_cycle


class Queue:
    def __init__(self):
        self.state = "queued"
    def get(self, job_id):
        return {"task": "review", "state": self.state}


class AuthorisedQueueCycleTests(unittest.TestCase):
    def run_cycle(self, selection, cycle):
        q = Queue()
        with patch("agent.authorised_queue_cycle.select_for_provider_review",
                   return_value=selection):
            return run_next_authorised_cycle(
                queue_db="/unused/queue", job_db="/unused/jobs",
                control_db="/unused/stop", task_queue=q,
                require_running=lambda: None,
                authorised_cycle=lambda job_id: cycle(q, job_id))

    def test_empty_never_executes(self):
        def forbidden(*args):
            raise AssertionError("must not dispatch")
        self.assertEqual(self.run_cycle({"state": "empty"}, forbidden),
                         {"state": "empty"})

    def test_success_requires_durable_done(self):
        def cycle(q, job):
            q.state = "done"
            return SimpleNamespace(job_id=job, state="done",
                                   draft_pr={"draft": True})
        result = self.run_cycle(
            {"state": "queued_for_review", "job_id": "job1", "task": "review"},
            cycle)
        self.assertEqual(result["draft_pr"], {"draft": True})

    def test_claimed_or_stale_job_rejected(self):
        def cycle(q, job):
            return SimpleNamespace(job_id=job, state="done",
                                   draft_pr={"draft": True})
        with self.assertRaises(PermissionError):
            self.run_cycle(
                {"state": "queued_for_review", "job_id": "job1", "task": "review"},
                cycle)

    def test_blocked_job_never_delivers_pr(self):
        def cycle(q, job):
            q.state = "blocked"
            return SimpleNamespace(job_id=job, state="blocked", draft_pr=None)
        result = self.run_cycle(
            {"state": "queued_for_review", "job_id": "job1", "task": "review"},
            cycle)
        self.assertEqual(result["state"], "blocked")
        self.assertIsNone(result["draft_pr"])

    def test_done_without_confirmed_draft_rejected(self):
        def cycle(q, job):
            q.state = "done"
            return SimpleNamespace(job_id=job, state="done", draft_pr=None)
        with self.assertRaises(PermissionError):
            self.run_cycle({"state": "queued_for_review", "job_id": "job1", "task": "review"}, cycle)

    def test_blocked_with_pr_rejected(self):
        def cycle(q, job):
            q.state = "blocked"
            return SimpleNamespace(job_id=job, state="blocked", draft_pr={"draft": True})
        with self.assertRaises(PermissionError):
            self.run_cycle({"state": "queued_for_review", "job_id": "job1", "task": "review"}, cycle)

    def test_no_authorised_cycle_rejected(self):
        with self.assertRaises(PermissionError):
            run_next_authorised_cycle(
                queue_db="x", job_db="y", control_db="z",
                task_queue=Queue(), require_running=lambda: None,
                authorised_cycle=None)


if __name__ == "__main__":
    unittest.main()
