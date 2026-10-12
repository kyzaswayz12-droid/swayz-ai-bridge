import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from pathlib import Path
from agent.gbp_budget import GBPBudget

NOW = datetime(2026, 10, 12, 22, tzinfo=timezone.utc)


class GBPBudgetConcurrencyTests(unittest.TestCase):
    def test_concurrent_separate_connections_never_exceed_five_pounds(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "budget.sqlite")

            def reserve(i):
                store = GBPBudget(path)
                try:
                    try:
                        return store.reserve(str(i), "openai" if i % 2 else "anthropic",
                                             D("1"), D("1"), NOW)
                    except ValueError as error:
                        if "exhausted" in str(error):
                            return False
                        raise
                finally:
                    store.close()

            with ThreadPoolExecutor(max_workers=10) as pool:
                results = list(pool.map(reserve, range(20)))
            self.assertEqual(sum(results), 5)

    def test_utc_day_rollover(self):
        with tempfile.TemporaryDirectory() as d:
            store = GBPBudget(str(Path(d) / "budget.sqlite"))
            self.assertTrue(store.reserve("day-one", "openai", D("5"), D("1"), NOW))
            self.assertTrue(store.reserve("day-two", "anthropic", D("5"), D("1"),
                                          NOW + timedelta(days=1)))
            store.close()
