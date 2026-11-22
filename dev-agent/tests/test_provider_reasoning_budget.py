"""Regression tests for the incomplete reasoning-only OpenAI response (2026-11-22).

Offline only: no provider HTTP, credentials, Docker, GitHub writes or billing.
"""
import json
import unittest
from decimal import Decimal

from agent.providers import openai_response, prepare_openai_request
from agent.collaboration_cost_preview import preview_task
from agent.split_provider_authority import MAX_USD, TASK


class ProviderReasoningBudgetTests(unittest.TestCase):
    def test_incomplete_reasoning_only_response_fails_closed(self):
        raw = {
            "status": "incomplete",
            "output": [{"type": "reasoning"}],
            "usage": {
                "input_tokens": 148,
                "output_tokens": 1024,
                "output_tokens_details": {"reasoning_tokens": 1024},
            },
        }
        with self.assertRaisesRegex(ValueError, "incomplete or not completed"):
            openai_response(json.dumps(raw).encode("utf-8"))

    def test_completed_response_with_visible_text(self):
        raw = {
            "status": "completed",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": '{"ok":true}'}
            ]}],
            "usage": {"input_tokens": 148, "output_tokens": 1140},
        }
        result = openai_response(json.dumps(raw).encode("utf-8"))
        self.assertEqual(result.text, '{"ok":true}')
        self.assertEqual((result.input_tokens, result.output_tokens), (148, 1140))

    def test_request_uses_low_reasoning_and_matching_output_budget(self):
        request = prepare_openai_request("gpt-5-mini", "Provide JSON", TASK, max_output_tokens=3072)
        self.assertEqual(request["max_output_tokens"], 3072)
        self.assertEqual(request["reasoning"], {"effort": "low"})
        self.assertIs(request["store"], False)

    def test_preview_accounts_for_increased_output_and_stays_under_ceiling(self):
        quote = preview_task(TASK)
        self.assertEqual(quote.total_reservation_usd, Decimal("0.042586"))
        self.assertLessEqual(quote.total_reservation_usd, MAX_USD)


if __name__ == "__main__":
    unittest.main()
