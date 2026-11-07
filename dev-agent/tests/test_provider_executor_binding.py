import unittest
from unittest.mock import patch
from agent.provider_backed_development_cycle import run_provider_backed_cycle

class ProviderExecutorBindingTests(unittest.TestCase):
    def test_conflicting_execution_paths_rejected_before_paid_calls(self):
        with patch("agent.provider_backed_development_cycle.dispatch_reserved_provider_once") as dispatch:
            with self.assertRaises(PermissionError):
                run_provider_backed_cycle(
                    job_id="j1", task_queue=object(), require_running=lambda:None,
                    job_db="unused", budget_db="unused", control_db="unused",
                    fx_approval_path="unused", now=None, base_branch="main",
                    base_sha="a"*40, openai_model="test", anthropic_model="test",
                    openai_key="test", anthropic_key="test",
                    openai_maximum_usd=None, anthropic_maximum_usd=None,
                    run_verified_tests=lambda **kw:None,
                    operator_prepared_executor={}, github=object(),
                    owner_approved=True, paid_calls_enabled=True)
            dispatch.assert_not_called()

    def test_missing_verified_executor_rejected_before_paid_calls(self):
        with patch("agent.provider_backed_development_cycle.dispatch_reserved_provider_once") as dispatch:
            with self.assertRaises(PermissionError):
                run_provider_backed_cycle(
                    job_id="j1", task_queue=object(), require_running=lambda:None,
                    job_db="unused", budget_db="unused", control_db="unused",
                    fx_approval_path="unused", now=None, base_branch="main",
                    base_sha="a"*40, openai_model="test", anthropic_model="test",
                    openai_key="test", anthropic_key="test",
                    openai_maximum_usd=None, anthropic_maximum_usd=None,
                    run_verified_tests=None, github=object(),
                    owner_approved=True, paid_calls_enabled=True)
            dispatch.assert_not_called()

    def test_paid_gate_still_rejects_operator_preparation(self):
        with patch("agent.provider_backed_development_cycle.dispatch_reserved_provider_once") as dispatch:
            with self.assertRaises(PermissionError):
                run_provider_backed_cycle(
                    job_id="j1", task_queue=object(), require_running=lambda:None,
                    job_db="unused", budget_db="unused", control_db="unused",
                    fx_approval_path="unused", now=None, base_branch="main",
                    base_sha="a"*40, openai_model="test", anthropic_model="test",
                    openai_key="test", anthropic_key="test",
                    openai_maximum_usd=None, anthropic_maximum_usd=None,
                    run_verified_tests=None, operator_prepared_executor={},
                    github=object())
            dispatch.assert_not_called()
