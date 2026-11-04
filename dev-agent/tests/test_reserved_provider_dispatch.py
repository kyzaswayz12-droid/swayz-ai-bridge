"""No-network integration checks for the real one-shot provider dispatcher."""
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from agent.reserved_provider_dispatch import dispatch_reserved_provider_once


class ReservedProviderDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.jobs = str(root / "jobs.db")
        self.budget = str(root / "budget.db")
        self.stop = str(root / "stop.db")
        self.fx = str(root / "fx.json")
        self.now = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
        with sqlite3.connect(self.jobs) as db:
            db.execute("CREATE TABLE admitted_jobs(job_id TEXT PRIMARY KEY, day_utc TEXT)")
            db.execute("INSERT INTO admitted_jobs VALUES('job1','2026-11-04')")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY, stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")
        Path(self.fx).write_text(json.dumps({
            "base":"USD","quote":"GBP","gbp_per_usd":"0.80",
            "verified_by_owner":True,"verified_on":"2026-11-04",
            "expires_on":"2026-11-04","source_url":"https://example.com/fx"}))
        self.calls = 0

    def transport(self, provider, payload, key):
        self.calls += 1
        return json.dumps({"output":[{"content":[{"type":"output_text","text":"approved"}]}],
                           "usage":{"input_tokens":3,"output_tokens":2}}).encode()

    def dispatch(self, **changes):
        args = dict(job_db=self.jobs,budget_db=self.budget,control_db=self.stop,
                    fx_approval_path=self.fx,job_id="job1",request_id="request1",
                    provider="openai",model="gpt-5-mini",instruction="Review",
                    task="Fix tests",maximum_usd=Decimal("0.20"),now=self.now,
                    api_key="fake-test-key",owner_approved=True,
                    paid_calls_enabled=True,transport=self.transport)
        args.update(changes)
        return dispatch_reserved_provider_once(**args)

    def test_one_call_with_gbp_reservation(self):
        result = self.dispatch()
        self.assertEqual(result.response.text,"approved")
        self.assertEqual(self.calls,1)
        with sqlite3.connect(self.budget) as db:
            self.assertEqual(db.execute(
                "SELECT reserved_gbp,status FROM gbp_reservations").fetchone(),
                ("0.1600","reserved"))

    def test_duplicate_request_not_retried(self):
        self.dispatch()
        with self.assertRaises(ValueError):
            self.dispatch()
        self.assertEqual(self.calls,1)

    def test_no_approval_no_reservation(self):
        with self.assertRaises(PermissionError):
            self.dispatch(owner_approved=False)
        self.assertEqual(self.calls,0)
        self.assertFalse(Path(self.budget).exists())

    def test_engaged_stop_prevents_call(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=1")
        with self.assertRaises(PermissionError):
            self.dispatch()
        self.assertEqual(self.calls,0)

    def test_missing_job_admission_blocks_call(self):
        with self.assertRaises(PermissionError):
            self.dispatch(job_id="missing")
        self.assertEqual(self.calls,0)

    def test_transport_failure_retains_reservation(self):
        def fail(*args):
            raise RuntimeError("Network uncertain")
        with self.assertRaises(RuntimeError):
            self.dispatch(transport=fail)
        with sqlite3.connect(self.budget) as db:
            self.assertEqual(db.execute(
                "SELECT status FROM gbp_reservations").fetchone(),("reserved",))
