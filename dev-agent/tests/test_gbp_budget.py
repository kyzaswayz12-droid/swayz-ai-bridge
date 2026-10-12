import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from agent.gbp_budget import GBPBudget


NOW = datetime(2026, 10, 12, 22, tzinfo=timezone.utc)


class GBPBudgetTests(unittest.TestCase):
    def test_combined_provider_cap_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "budget.sqlite")
            a = GBPBudget(path)
            self.assertTrue(a.reserve("a", "openai", D("3"), D("1"), NOW))
            a.close()
            b = GBPBudget(path)
            self.assertFalse(b.reserve("a", "openai", D("3"), D("1"), NOW))
            self.assertTrue(b.reserve("b", "anthropic", D("2"), D("1"), NOW))
            with self.assertRaisesRegex(ValueError, "exhausted"):
                b.reserve("c", "openai", D("0.01"), D("1"), NOW)
            b.close()

    def test_settlement_releases_unused_reservation(self):
        with tempfile.TemporaryDirectory() as d:
            b = GBPBudget(str(Path(d) / "budget.sqlite"))
            b.reserve("a", "openai", D("4"), D("1"), NOW)
            b.settle("a", D("2"))
            self.assertTrue(b.reserve("b", "anthropic", D("3"), D("1"), NOW))
            with self.assertRaises(ValueError):
                b.settle("b", D("3.01"))
            b.close()

    def test_invalid_rate_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            b = GBPBudget(str(Path(d) / "budget.sqlite"))
            for rate in (D("NaN"), D("0"), D("-1")):
                with self.assertRaises(ValueError):
                    b.reserve("bad", "openai", D("1"), rate, NOW)
            b.close()
