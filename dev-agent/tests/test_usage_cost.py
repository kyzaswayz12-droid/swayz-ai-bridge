import unittest
from decimal import Decimal as D
from agent.cost_estimates import RateCard
from agent.usage_cost import calculate_usage_cost

class UsageCostTests(unittest.TestCase):
    def test_token_estimate_not_billing_verification(self):
        card=RateCard("example-model",D("1"),D("4"))
        result=calculate_usage_cost("openai",card,model="example-model",
                                    input_tokens=1000,output_tokens=500)
        self.assertEqual(result.estimated_usd,D("0.003000"))
        self.assertFalse(result.billing_verified)

    def test_wrong_model_rejected(self):
        card=RateCard("example-model",D("1"),D("4"))
        with self.assertRaises(ValueError):
            calculate_usage_cost("openai",card,model="other",
                                 input_tokens=100,output_tokens=100)

    def test_unknown_provider_rejected(self):
        card=RateCard("example-model",D("1"),D("4"))
        with self.assertRaises(ValueError):
            calculate_usage_cost("unknown",card,model="example-model",
                                 input_tokens=100,output_tokens=100)
