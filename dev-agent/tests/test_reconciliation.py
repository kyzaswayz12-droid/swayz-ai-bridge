import unittest
from decimal import Decimal as D
from agent.cost_estimates import RateCard
from agent.usage_cost import calculate_usage_cost
from agent.reconciliation import propose_reconciliation

class ReconciliationTests(unittest.TestCase):
    def test_estimate_never_releases_unverified_hold(self):
        usage=calculate_usage_cost("openai",RateCard("example",D("1"),D("4")),
                                  model="example",input_tokens=1000,output_tokens=500)
        result=propose_reconciliation("request-1",D("0.10"),usage)
        self.assertEqual(result.estimated_usd,D("0.003000"))
        self.assertEqual(result.releasable_usd,D("0"))
        self.assertEqual(result.status,"awaiting_provider_verification")

    def test_bad_reservation_rejected(self):
        usage=calculate_usage_cost("anthropic",RateCard("example",D("1"),D("4")),
                                  model="example",input_tokens=10,output_tokens=10)
        with self.assertRaises(ValueError):
            propose_reconciliation("request-1",D("-1"),usage)
