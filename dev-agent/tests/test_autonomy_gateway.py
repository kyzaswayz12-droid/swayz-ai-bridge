import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from agent.autonomy_gateway import reserve_offline_gateway_request
from agent.daily_job_quota import DailyJobQuota
from agent.emergency_stop import EmergencyStop
from agent.gbp_budget import GBPBudget

NOW = datetime(2026, 10, 12, 22, tzinfo=timezone.utc)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.job_db = str(root / "jobs.sqlite")
        self.budget_db = str(root / "budget.sqlite")
        self.control_db = str(root / "control.sqlite")
        jobs = DailyJobQuota(self.job_db)
        jobs.admit("job1", NOW)
        jobs.close()
        self.args = dict(job_db=self.job_db, budget_db=self.budget_db,
                         control_db=self.control_db, job_id="job1",
                         request_id="req1", provider="openai",
                         model="test-model", instruction="Review", task="Mock task",
                         maximum_usd=D("1"), approved_gbp_per_usd=D("1"), now=NOW)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_control_fails_closed(self):
        with self.assertRaises(PermissionError):
            reserve_offline_gateway_request(**self.args)

    def test_stopped_control_fails_without_reservation(self):
        control = EmergencyStop(self.control_db)
        control.close()
        with self.assertRaises(PermissionError):
            reserve_offline_gateway_request(**self.args)
        budget = GBPBudget(self.budget_db)
        self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM gbp_reservations").fetchone()[0], 0)
        budget.close()

    def test_enabled_control_allows_offline_reservation_only(self):
        control = EmergencyStop(self.control_db)
        control.enable(owner_authorised=True)
        control.close()
        result = reserve_offline_gateway_request(**self.args)
        self.assertTrue(result.reserved)
        self.assertEqual(result.provider_calls, 0)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            reserve_offline_gateway_request(**self.args)
