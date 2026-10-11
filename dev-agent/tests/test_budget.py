import tempfile
from pathlib import Path
import unittest
from datetime import datetime, timezone
from decimal import Decimal as D
from agent.budget import BudgetStore, BudgetLimits

NOW = datetime(2026,10,10,21,0,tzinfo=timezone.utc)

class BudgetTests(unittest.TestCase):
    def test_reservation_is_durable_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/"budget.db")
            a=BudgetStore(p)
            limits=BudgetLimits(D("1"),2,D("0.6"))
            self.assertTrue(a.reserve("one",D("0.6"),limits,NOW))
            self.assertFalse(a.reserve("one",D("0.6"),limits,NOW))
            a.close()
            b=BudgetStore(p)
            with self.assertRaisesRegex(ValueError,"exhausted"):
                b.reserve("two",D("0.6"),limits,NOW)
            b.settle("one",D("0.2"))
            self.assertTrue(b.reserve("two",D("0.6"),limits,NOW))
            with self.assertRaisesRegex(ValueError,"exhausted"):
                b.reserve("three",D("0.1"),limits,NOW)
            b.close()

    def test_over_reservation_cannot_settle(self):
        b=BudgetStore()
        b.reserve("one",D("0.2"),BudgetLimits(),NOW)
        with self.assertRaises(ValueError):
            b.settle("one",D("0.3"))
        with self.assertRaises(ValueError):
            b.reserve("bad",D("NaN"),BudgetLimits(),NOW)
        b.close()

    def test_naive_clock_rejected(self):
        b=BudgetStore()
        with self.assertRaises(ValueError):
            b.reserve("one",D("0.1"),BudgetLimits(),datetime(2026,10,10))
        b.close()
