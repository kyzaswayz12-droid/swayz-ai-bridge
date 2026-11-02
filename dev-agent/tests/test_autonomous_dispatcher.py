import json
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from agent.job_request_reservation import admit_job
from agent.autonomous_dispatcher import simulate_review_request
from agent.emergency_stop import EmergencyStop

NOW = datetime(2026, 10, 12, 22, tzinfo=timezone.utc)


class AutonomousDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.jobs = str(root / "jobs.db")
        self.budget = str(root / "budget.db")
        self.control_db = str(root / "control.db")
        control = EmergencyStop(self.control_db)
        control.enable(owner_authorised=True)
        control.close()
        self.assertTrue(admit_job(job_db=self.jobs, job_id="job1", now=NOW))

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, request_id, provider, amount=D("1")):
        if provider == "openai":
            response = {"output": [{"content": [{"type": "output_text", "text": "Proposal"}]}],
                        "usage": {"input_tokens": 10, "output_tokens": 2}}
        else:
            response = {"content": [{"type": "text", "text": "Review"}],
                        "usage": {"input_tokens": 10, "output_tokens": 2}}
        return simulate_review_request(
            job_db=self.jobs, budget_db=self.budget, control_db=self.control_db, job_id="job1",
            request_id=request_id, provider=provider, model="test-model",
            instruction="Review", task="Mock code", maximum_usd=amount,
            approved_gbp_per_usd=D("1"), now=NOW,
            mock_response=json.dumps(response).encode())

    def test_both_providers_share_one_job(self):
        self.assertEqual(self.call("req1", "openai").response.text, "Proposal")
        self.assertEqual(self.call("req2", "anthropic").response.text, "Review")

    def test_duplicate_request_rejected(self):
        self.call("req1", "openai")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.call("req1", "openai")

    def test_budget_exhaustion(self):
        self.call("req1", "openai", D("4"))
        with self.assertRaisesRegex(ValueError, "exhausted"):
            self.call("req2", "anthropic", D("2"))
