import json
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from agent.autonomous_dispatcher import simulate_review_request
from agent.job_request_reservation import admit_job
from agent.emergency_stop import EmergencyStop
from agent.gbp_budget import GBPBudget

NOW = datetime(2026, 10, 12, 22, tzinfo=timezone.utc)


class AutonomousEmergencyStopTests(unittest.TestCase):
    def test_stopped_agent_refuses_before_spending_reservation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            job_db, budget_db, control_db = [str(root / name)
                for name in ("jobs.db", "budget.db", "control.db")]
            admit_job(job_db=job_db, job_id="job1", now=NOW)
            control = EmergencyStop(control_db)
            self.assertTrue(control.is_stopped())
            control.close()
            mock = json.dumps({
                "output": [{"content": [{"type": "output_text", "text": "Proposal"}]}],
                "usage": {"input_tokens": 10, "output_tokens": 2}
            }).encode()
            with self.assertRaises(PermissionError):
                simulate_review_request(
                    job_db=job_db, budget_db=budget_db, control_db=control_db,
                    job_id="job1", request_id="req1", provider="openai",
                    model="test-model", instruction="Review", task="Mock code",
                    maximum_usd=D("1"), approved_gbp_per_usd=D("1"),
                    now=NOW, mock_response=mock)
            ledger = GBPBudget(budget_db)
            count = ledger.db.execute(
                "SELECT COUNT(*) FROM gbp_reservations").fetchone()[0]
            self.assertEqual(count, 0)
            ledger.close()
