import json
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from agent.emergency_stop import EmergencyStop
from agent.offline_autonomy_workflow import stage_offline_collaboration

NOW = datetime(2026, 10, 12, 22, tzinfo=timezone.utc)


class OfflineAutonomyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.control = str(root / "control.db")
        self.fx = root / "fx.json"
        self.fx.write_text(json.dumps({
            "base": "USD", "quote": "GBP", "gbp_per_usd": "1.00",
            "verified_by_owner": True, "verified_on": "2026-10-12",
            "expires_on": "2026-10-13", "source_url": "https://example.org/fx"
        }), encoding="utf-8")
        self.args = dict(job_db=str(root / "jobs.db"),
                         budget_db=str(root / "budget.db"),
                         control_db=self.control, fx_approval_path=str(self.fx),
                         job_id="job1", openai_request_id="req1",
                         anthropic_request_id="req2", openai_model="test-openai",
                         anthropic_model="test-claude", task="Review proposed change",
                         openai_maximum_usd=D("1"),
                         anthropic_maximum_usd=D("1"), now=NOW)

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_reservations_no_execution(self):
        control = EmergencyStop(self.control)
        control.enable(owner_authorised=True)
        control.close()
        result = stage_offline_collaboration(**self.args)
        self.assertEqual(result.reserved_requests, 2)
        self.assertEqual(result.provider_calls, 0)
        self.assertFalse(result.docker_executed)
        self.assertEqual(result.github_writes, 0)

    def test_stopped_agent_refuses_before_job_admission(self):
        control = EmergencyStop(self.control)
        control.close()
        with self.assertRaises(PermissionError):
            stage_offline_collaboration(**self.args)

    def test_duplicate_job_rejected(self):
        control = EmergencyStop(self.control)
        control.enable(owner_authorised=True)
        control.close()
        stage_offline_collaboration(**self.args)
        with self.assertRaisesRegex(ValueError, "Duplicate development job"):
            stage_offline_collaboration(**self.args)
