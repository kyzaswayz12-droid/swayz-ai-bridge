import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from pathlib import Path
from agent.job_request_reservation import admit_job, reserve_job_api_request

NOW = datetime(2026, 10, 12, 22, tzinfo=timezone.utc)


class JobRequestReservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.jobs = str(root / "jobs.db")
        self.budget = str(root / "budget.db")

    def tearDown(self):
        self.temp.cleanup()

    def reserve(self, job, request, provider="openai", now=NOW):
        return reserve_job_api_request(
            job_db=self.jobs, budget_db=self.budget, job_id=job,
            request_id=request, provider=provider, maximum_usd=D("1"),
            approved_gbp_per_usd=D("1"), now=now)

    def test_multiple_providers_one_job_slot(self):
        self.assertTrue(admit_job(job_db=self.jobs, job_id="job1", now=NOW))
        self.assertTrue(self.reserve("job1", "req1", "openai"))
        self.assertTrue(self.reserve("job1", "req2", "anthropic"))
        self.assertFalse(admit_job(job_db=self.jobs, job_id="job1", now=NOW))

    def test_unadmitted_job_refused(self):
        with self.assertRaises(PermissionError):
            self.reserve("unknown", "req1")

    def test_duplicate_request_refused(self):
        admit_job(job_db=self.jobs, job_id="job1", now=NOW)
        self.assertTrue(self.reserve("job1", "req1"))
        self.assertFalse(self.reserve("job1", "req1"))

    def test_old_day_job_refused(self):
        admit_job(job_db=self.jobs, job_id="job1", now=NOW)
        with self.assertRaises(PermissionError):
            self.reserve("job1", "req1", now=NOW + timedelta(days=1))
