import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from agent.autonomy_preflight import preflight_job_request

NOW = datetime(2026, 10, 12, 22, tzinfo=timezone.utc)


class AutonomyPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.args = dict(job_db=str(root / "jobs.db"),
                         budget_db=str(root / "budget.db"),
                         provider="openai", maximum_usd=D("1"),
                         approved_gbp_per_usd=D("1"), now=NOW)

    def tearDown(self):
        self.tmp.cleanup()

    def test_offline_admission_never_dispatches(self):
        result = preflight_job_request(**self.args, job_id="job1", request_id="req1")
        self.assertTrue(result.job_admitted)
        self.assertTrue(result.request_reserved)
        self.assertEqual(result.provider_calls, 0)

    def test_duplicate_job_rejected(self):
        preflight_job_request(**self.args, job_id="job1", request_id="req1")
        with self.assertRaisesRegex(ValueError, "Duplicate development job"):
            preflight_job_request(**self.args, job_id="job1", request_id="req2")

    def test_duplicate_request_rejected(self):
        preflight_job_request(**self.args, job_id="job1", request_id="req1")
        with self.assertRaisesRegex(ValueError, "Duplicate API request"):
            preflight_job_request(**self.args, job_id="job2", request_id="req1")

    def test_budget_exhaustion_rejected(self):
        preflight_job_request(**self.args, job_id="job1", request_id="req1")
        with self.assertRaisesRegex(ValueError, "exhausted"):
            preflight_job_request(**{**self.args, "maximum_usd": D("5")},
                                  job_id="job2", request_id="req2")

    def test_enabled_execution_refused(self):
        with self.assertRaises(PermissionError):
            preflight_job_request(**self.args, job_id="job1", request_id="req1",
                                  enabled=True)
