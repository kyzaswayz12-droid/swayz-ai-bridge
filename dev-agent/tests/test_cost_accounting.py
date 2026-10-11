import unittest
from datetime import datetime,timezone
from decimal import Decimal as D
from agent.cost_estimates import RateCard,estimated_cost,reservation_for_request
from agent.budget import BudgetStore,BudgetLimits

class CostAccountingTests(unittest.TestCase):
    def test_decimal_cost_and_safety_margin(self):
        card=RateCard("example",D("1"),D("4"))
        self.assertEqual(estimated_cost(card,1000,500),D("0.003000"))
        self.assertEqual(reservation_for_request(card,1000,500),D("0.006000"))

    def test_bad_rates_and_counts_fail_closed(self):
        with self.assertRaises(ValueError):
            RateCard("example",D("NaN"),D("2"))
        with self.assertRaises(ValueError):
            estimated_cost(RateCard("example",D("1"),D("2")),-1,10)

    def test_pending_and_settled_are_separate(self):
        ledger=BudgetStore()
        now=datetime(2026,10,11,tzinfo=timezone.utc)
        ledger.reserve("a",D("0.10"),BudgetLimits(),now)
        ledger.reserve("b",D("0.10"),BudgetLimits(),now)
        before=ledger.summary("2026-10-11")
        self.assertEqual(before["pending_reserved_usd"],"0.20")
        self.assertEqual(before["settled_usd"],"0")
        ledger.settle("a",D("0.003"))
        after=ledger.summary("2026-10-11")
        self.assertEqual(after["pending_reserved_usd"],"0.10")
        self.assertEqual(after["settled_usd"],"0.003")
        self.assertEqual(after["accounted_usd"],"0.103")
        self.assertFalse(after["actual_provider_billing_verified"])
        ledger.close()

    def test_unknown_charge_remains_reserved(self):
        ledger=BudgetStore()
        now=datetime(2026,10,11,tzinfo=timezone.utc)
        ledger.reserve("uncertain",D("0.10"),BudgetLimits(),now)
        self.assertEqual(ledger.summary("2026-10-11")["pending_reserved_usd"],"0.10")
        ledger.close()
