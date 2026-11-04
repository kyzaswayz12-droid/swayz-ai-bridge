"""No paid calls or GitHub writes: integration smoke for provider-backed cycle."""
import json
import unittest
from unittest.mock import patch
from agent.provider_backed_development_cycle import run_provider_backed_cycle
from agent.providers import ModelResponse
from types import SimpleNamespace


class Queue:
    def get(self, job_id):
        return {"state":"queued","task":"Fix a test"}


class ProviderBackedCycleTests(unittest.TestCase):
    def args(self):
        return dict(job_id="job1",task_queue=Queue(),
            require_running=lambda:None,job_db="/tmp/not-used",
            budget_db="/tmp/not-used",control_db="/tmp/not-used",
            fx_approval_path="/tmp/not-used",now=__import__("datetime").datetime(
                2026,11,4,tzinfo=__import__("datetime").timezone.utc),
            base_branch="main",base_sha="a"*40,openai_model="gpt-5-mini",
            anthropic_model="claude-haiku-4-5",openai_key="test",anthropic_key="test",
            openai_maximum_usd=__import__("decimal").Decimal("0.1"),
            anthropic_maximum_usd=__import__("decimal").Decimal("0.1"),
            run_verified_tests=lambda **k:{"state":"passed","cleanup_verified":True},
            github=object())

    @patch("agent.provider_backed_development_cycle.complete_supervised_cycle")
    @patch("agent.provider_backed_development_cycle.dispatch_reserved_provider_once")
    def test_dispatches_two_reserved_calls_then_coordinator(self, dispatch, cycle):
        proposal=json.dumps(dict(base_sha="a"*40,proposal_sha256="b"*64,
            branch="agent/fix-test",changes=[dict(path="tests/fix.py",content="assert True")]))
        review=json.dumps(dict(proposal_sha256="b"*64,approved=True,findings=[]))
        dispatch.side_effect=[
            SimpleNamespace(response=ModelResponse(proposal,10,10)),
            SimpleNamespace(response=ModelResponse(review,10,10))]
        self_args=self.args()
        self_args.update(owner_approved=True,paid_calls_enabled=True)
        run_provider_backed_cycle(**self_args)
        self.assertEqual(dispatch.call_count,2)
        self.assertEqual(dispatch.call_args_list[0].kwargs["request_id"],"job1-openai")
        self.assertEqual(dispatch.call_args_list[1].kwargs["request_id"],"job1-anthropic")
        reviewed = json.loads(dispatch.call_args_list[1].kwargs["task"])
        import hashlib
        canonical = json.dumps({k:v for k,v in reviewed.items() if k != "proposal_sha256"}, sort_keys=True, separators=(",",":"), ensure_ascii=True)
        self.assertEqual(reviewed["proposal_sha256"], hashlib.sha256(canonical.encode()).hexdigest())
        cycle.assert_called_once()

    @patch("agent.provider_backed_development_cycle.dispatch_reserved_provider_once")
    def test_disabled_by_default(self, dispatch):
        with self.assertRaises(PermissionError):
            run_provider_backed_cycle(**self.args())
        dispatch.assert_not_called()

    @patch("agent.provider_backed_development_cycle.dispatch_reserved_provider_once")
    def test_invalid_coding_proposal_prevents_second_paid_call(self, dispatch):
        dispatch.return_value=SimpleNamespace(response=ModelResponse("not json",1,1))
        with self.assertRaises(ValueError):
            run_provider_backed_cycle(**dict(self.args(),owner_approved=True,
                                              paid_calls_enabled=True))
        self.assertEqual(dispatch.call_count,1)
