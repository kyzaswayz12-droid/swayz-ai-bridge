import unittest
from decimal import Decimal as D
from agent.reference_rates import reference_rate
from agent.cost_estimates import reservation_for_request

class ReferenceRatesTests(unittest.TestCase):
    def test_openai_small_request(self):
        card=reference_rate("openai","gpt-5-mini")
        self.assertEqual(reservation_for_request(card,2000,1024),D("0.005096"))

    def test_claude_small_request(self):
        card=reference_rate("anthropic","claude-haiku-4-5-20251001")
        self.assertEqual(reservation_for_request(card,2000,512),D("0.009120"))

    def test_unknown_model_fails_closed(self):
        with self.assertRaises(ValueError):
            reference_rate("openai","unknown")
