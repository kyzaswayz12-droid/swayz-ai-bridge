import json
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from agent.daily_job_quota import DailyJobQuota
from agent.emergency_stop import EmergencyStop
from agent.offline_autonomy_workflow import stage_offline_collaboration

NOW = datetime(2026, 10, 12, 22, tzinfo=timezone.utc)


class WorkflowFailureBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.job_db = str(root / "jobs.db")
        self.control_db = str(root / "control.db")
        self.fx_path = root / "fx.json"
        self.fx_path.write_text(json.dumps({
            "base": "USD", "quote": "GBP", "gbp_per_usd": "1.00",
            "verified_by_owner": True, "verified_on": "2026-10-12",
            "expires_on": "2026-10-13", "source_url": "https://example.org/fx"
        }), encoding="utf-8")
        control = EmergencyStop(self.control_db)
        control.enable(owner_authorised=True)
        control.close()
        self.args = dict(job_db=self.job_db, budget_db=str(root / "budget.db"),
                         control_db=self.control_db, fx_approval_path=str(self.fx_path),
                         job_id="job1", openai_request_id="req1",
                         anthropic_request_id="req2", openai_model="openai-test",
                         anthropic_model="claude-test", task="Review code",
                         openai_maximum_usd=D("1"), anthropic_maximum_usd=D("1"),
                         now=NOW)

    def tearDown(self):
        self.temp.cleanup()

    def admitted(self):
        store = DailyJobQuota(self.job_db)
        try:
            return store.db.execute("SELECT COUNT(*) FROM admitted_jobs").fetchone()[0]
        finally:
            store.close()

    def test_excessive_combined_cost_rejected_before_admission(self):
        with self.assertRaisesRegex(ValueError, "Combined request maximum"):
            stage_offline_collaboration(**{**self.args, "openai_maximum_usd": D("4"),
                                           "anthropic_maximum_usd": D("2")})
        self.assertEqual(self.admitted(), 0)

    def test_invalid_model_rejected_before_admission(self):
        with self.assertRaises(ValueError):
            stage_offline_collaboration(**{**self.args, "openai_model": ""})
        self.assertEqual(self.admitted(), 0)

    def test_expired_fx_rejected_before_admission(self):
        with self.assertRaises(PermissionError):
            stage_offline_collaboration(**{**self.args,
                "now": datetime(2026, 10, 15, tzinfo=timezone.utc)})
        self.assertEqual(self.admitted(), 0)

    def test_duplicate_request_ids_rejected_before_admission(self):
        with self.assertRaises(ValueError):
            stage_offline_collaboration(**{**self.args, "anthropic_request_id": "req1"})
        self.assertEqual(self.admitted(), 0)
