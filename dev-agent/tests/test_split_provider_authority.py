"""Read-only split-authority protocol tests. No network, Docker, credentials disclosure."""
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent.split_provider_authority import issue_split_grant, consume_split_grant

NOW = datetime(2026, 11, 22, 17, 0, tzinfo=timezone.utc)
JOB = "dev-provider-test-1"
BASE = "a"*40


class SplitAuthorityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.grants, self.claims = root/"grants", root/"claims"
        self.grants.mkdir(mode=0o700)
        self.claims.mkdir(mode=0o700)
        self.budget = root/"budget.sqlite3"
        with sqlite3.connect(self.budget) as db:
            db.execute("""CREATE TABLE gbp_reservations(
                request_id TEXT PRIMARY KEY, provider TEXT NOT NULL,
                day_utc TEXT NOT NULL, reserved_gbp TEXT NOT NULL,
                status TEXT NOT NULL, actual_gbp TEXT)""")
        self.openai = root/"openai.json"
        self.claude = root/"claude.json"
        self.fx = root/"fx.json"
        self.creds = root/"providers.env"
        self.creds.write_text("OPENAI_API_KEY=dummy-openai\nANTHROPIC_API_KEY=dummy-claude\n")
        self.creds.chmod(0o600)
        common = dict(verified_on="2026-11-22", expires_on="2026-11-29",
                      verified_by_owner=True,source_url="https://example.com")
        self.openai.write_text(json.dumps({**common,
             "provider":"openai","model":"gpt-5-mini",
             "input_per_million_usd":"0.25","output_per_million_usd":"2.00"}))
        self.claude.write_text(json.dumps({**common,
             "provider":"anthropic","model":"claude-haiku-4-5-20251001",
             "input_per_million_usd":"1.00","output_per_million_usd":"5.00"}))
        self.fx.write_text(json.dumps({
             "base":"USD","quote":"GBP","gbp_per_usd":"0.80",**common}))
        self.key = Ed25519PrivateKey.generate()
        self.stopped = True
        self.verify_stop = self.require_stop
        self.signer = dict(job_id=JOB,base_sha=BASE,openai_card=self.openai,
            claude_card=self.claude,fx_card=self.fx,gbp_budget_db=self.budget,
            require_stop_engaged=self.verify_stop,verify_owner=lambda job: job==JOB,
            signing_key=self.key,now=NOW,output_directory=self.grants)

    def require_stop(self):
        if not self.stopped:
            raise PermissionError("Emergency stop not engaged")

    def sign(self, **overrides):
        args={**self.signer,**overrides}
        with patch("agent.split_provider_authority.os.geteuid",return_value=0):
            return issue_split_grant(**args)

    def verify(self,**overrides):
        args=dict(grant_bytes=(self.grants/(JOB+".grant.json")).read_bytes(),
            verification_key=self.key.public_key(),expected_job_id=JOB,
            expected_base_sha=BASE,credential_file=self.creds,
            require_stop_engaged=self.verify_stop,
            claimed_directory=self.claims,now=NOW+timedelta(seconds=1))
        args.update(overrides)
        return consume_split_grant(**args)

    def ledger(self):
        with sqlite3.connect(self.budget) as db:
            return db.execute("SELECT request_id,reserved_gbp,status FROM gbp_reservations ORDER BY request_id").fetchall()

    def test_root_reserves_twice_then_worker_consumes_once(self):
        result=self.sign()
        self.assertEqual(result["state"],"signed_grant_prepared")
        self.assertEqual(result["provider_calls"],0)
        rows=self.ledger()
        self.assertEqual(len(rows),2)
        self.assertTrue(all(x[2]=="reserved" for x in rows))
        self.assertLessEqual(sum(Decimal(x[1]) for x in rows),Decimal("0.05")*Decimal("0.80"))
        worker=self.verify()
        self.assertEqual(worker["state"],"claimed_for_operator_review")
        self.assertFalse(worker["live_dispatch_enabled"])
        self.assertEqual(worker["provider_calls"],0)
        with self.assertRaises(FileExistsError):
            self.verify()
        self.assertEqual(len(self.ledger()),2)
        self.assertTrue(self.stopped)

    def test_unapproved_does_not_reserve(self):
        with self.assertRaises(PermissionError):
            self.sign(verify_owner=lambda job:False)
        self.assertEqual(self.ledger(),[])

    def test_root_identity_required(self):
        with patch("agent.split_provider_authority.os.geteuid",return_value=1000):
            with self.assertRaises(PermissionError):
                issue_split_grant(**self.signer)
        self.assertEqual(self.ledger(),[])

    def test_missing_stop_blocks_both_roles(self):
        self.stopped=False
        with self.assertRaises(PermissionError):
            self.sign()
        self.assertEqual(self.ledger(),[])
        self.stopped=True
        self.sign()
        self.stopped=False
        with self.assertRaises(PermissionError):
            self.verify()

    def test_budget_exhaustion_prevents_grant(self):
        with sqlite3.connect(self.budget) as db:
            db.execute("INSERT INTO gbp_reservations VALUES(?,?,?,?,?,?)",
                      ("previous","openai","2026-11-22","5.00","reserved",None))
        with self.assertRaises(ValueError):
            self.sign()
        self.assertFalse((self.grants/(JOB+".grant.json")).exists())

    def test_signature_tamper_rejected(self):
        self.sign()
        raw=(self.grants/(JOB+".grant.json")).read_bytes().replace(
             b"swayz-provider-only-proposal",b"swayz-provider-only-proposax")
        with self.assertRaises(PermissionError):
            self.verify(grant_bytes=raw)
        self.assertFalse(list(self.claims.iterdir()))

    def test_other_job_or_base_rejected(self):
        self.sign()
        with self.assertRaises(PermissionError):
            self.verify(expected_job_id="other-job")
        with self.assertRaises(PermissionError):
            self.verify(expected_base_sha="b"*40)

    def test_expired_grant_rejected(self):
        self.sign()
        with self.assertRaises(PermissionError):
            self.verify(now=NOW+timedelta(minutes=11))
        self.assertFalse(list(self.claims.iterdir()))

    def test_credentials_must_remain_private_and_owned(self):
        self.sign()
        self.creds.chmod(0o644)
        with self.assertRaises(PermissionError):
            self.verify()
        self.assertFalse(list(self.claims.iterdir()))

    def test_no_grant_reissue_or_duplicate_holds(self):
        self.sign()
        with self.assertRaises(PermissionError):
            self.sign()
        self.assertEqual(len(self.ledger()),2)


if __name__=="__main__":
    unittest.main()
