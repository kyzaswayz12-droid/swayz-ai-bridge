import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from agent.daily_job_quota import DailyJobQuota


class DailyJobQuotaTests(unittest.TestCase):
    def test_restart_dedup_limit_and_rollover(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "jobs.sqlite")
            now = datetime(2026, 10, 12, 23, 30, tzinfo=timezone.utc)
            first = DailyJobQuota(path)
            self.assertTrue(first.admit("job-1", now, daily_limit=2))
            first.close()
            second = DailyJobQuota(path)
            self.assertFalse(second.admit("job-1", now, daily_limit=2))
            self.assertTrue(second.admit("job-2", now, daily_limit=2))
            with self.assertRaisesRegex(ValueError, "exhausted"):
                second.admit("job-3", now, daily_limit=2)
            self.assertTrue(second.admit("job-3", now + timedelta(hours=1), daily_limit=2))
            second.close()

    def test_invalid_clock_and_nonpersistent_store(self):
        with self.assertRaises(ValueError):
            DailyJobQuota(":memory:")
        with tempfile.TemporaryDirectory() as d:
            quota = DailyJobQuota(str(Path(d) / "jobs.sqlite"))
            with self.assertRaises(ValueError):
                quota.admit("job", datetime(2026, 10, 12))
            quota.close()
