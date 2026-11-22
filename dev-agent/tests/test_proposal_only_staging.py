"""Offline-only compatibility tests: no provider transport or executor."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from agent.proposal_only_staging import inspect_approvals, review_proposal


TASK = ("Create a self-contained Python development-job label validator and unit "
        "tests. Accept lowercase letters, digits and hyphens, 1 to 32 characters. "
        "Reject whitespace, path traversal and invalid characters. Return a "
        "structured JSON code-change proposal. Do not modify executor, "
        "credentials, security controls or trading code.")
JOB = "proposal-only-ci-1"
BASE = "a" * 40


class ProposalOnlyTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        root = Path(self.t.name)
        self.openai = root / "openai.json"
        self.claude = root / "claude.json"
        self.fx = root / "fx.json"
        self.stop = root / "stop.db"
        self.budget = root / "budget.db"
        self.output = root / "checkpoint"
        self.output.mkdir(mode=0o700)
        common = dict(verified_on="2026-11-22", expires_on="2099-12-31",
                      verified_by_owner=True, source_url="https://example.com/pricing")
        self.openai.write_text(json.dumps({**common, "provider": "openai",
            "model": "gpt-5-mini", "input_per_million_usd": "0.25",
            "output_per_million_usd": "2.00"}))
        self.claude.write_text(json.dumps({**common, "provider": "anthropic",
            "model": "claude-haiku-4-5-20251001", "input_per_million_usd": "1.00",
            "output_per_million_usd": "5.00"}))
        self.fx.write_text(json.dumps(dict(base="USD",quote="GBP",
            gbp_per_usd="0.80", verified_by_owner=True,
            verified_on="2026-11-22", expires_on="2099-12-31",
            source_url="https://example.com/fx")))
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY, stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,1)")
        with sqlite3.connect(self.budget) as db:
            db.execute("""CREATE TABLE gbp_reservations(
                request_id TEXT,provider TEXT,day_utc TEXT,reserved_gbp TEXT,
                status TEXT,actual_gbp TEXT)""")
        self.params = dict(task=TASK,openai_card=self.openai,claude_card=self.claude,
            fx_card=self.fx,stop_db=self.stop,gbp_budget_db=self.budget,
            now=datetime(2026,11,22,tzinfo=timezone.utc))
        self.proposal = {"base_sha": BASE, "branch": "agent/label-check-ci",
                         "changes": [{"path": "tests/test_job_label_ci.py",
                                      "content": "import unittest\nclass Label(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n"}]}
        c = json.dumps(self.proposal,sort_keys=True,separators=(",",":"),ensure_ascii=True)
        self.digest = hashlib.sha256(c.encode("ascii")).hexdigest()
        self.proposal["proposal_sha256"] = self.digest
        self.review = {"proposal_sha256":self.digest,"approved":True,"findings":[]}

    def approval(self):
        return inspect_approvals(**self.params)

    def stage(self, **kwargs):
        data=dict(job_id=JOB,task=TASK,base_sha=BASE,
                  proposal_text=json.dumps(self.proposal),
                  review_text=json.dumps(self.review),
                  approvals=self.approval(),checkpoint_dir=self.output)
        data.update(kwargs)
        return review_proposal(**data)

    def test_preflight_zero_calls_stop_engaged_and_below_cap(self):
        result=self.approval()
        self.assertEqual(result["state"],"preflight_passed")
        self.assertEqual(result["paid_calls"],0)
        self.assertFalse(result["execution_authorised"])
        self.assertLessEqual(Decimal(result["usd_reserved"]),Decimal("0.05"))
        self.assertEqual(Decimal(result["gbp_equivalent"]),
                         Decimal(result["usd_reserved"])*Decimal("0.80"))
        with sqlite3.connect(self.stop) as db:
            self.assertEqual(db.execute("SELECT stopped FROM agent_control").fetchone(),(1,))

    def test_review_creates_private_write_once_operator_checkpoint(self):
        approved=self.stage()
        self.assertEqual(approved["state"],"operator_review_required")
        data=json.loads(Path(approved["checkpoint"]).read_text())
        self.assertEqual(data["proposal_sha256"],self.digest)
        self.assertFalse(data["model_responses_authenticated"])
        self.assertFalse(data["execution_authorised"])
        self.assertEqual(data["github_writes"],0)
        self.assertEqual(data["paid_calls"],0)
        self.assertEqual(Path(approved["checkpoint"]).stat().st_mode & 0o777,0o600)
        with self.assertRaises(FileExistsError):
            self.stage()

    def test_engaged_stop_required(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=0")
        with self.assertRaises(PermissionError):
            self.approval()
        self.assertEqual(list(self.output.iterdir()),[])

    def test_rejected_review_fails_before_checkpoint(self):
        self.review["approved"]=False
        self.review["findings"]=["Rejected"]
        with self.assertRaises(PermissionError):
            self.stage()
        self.assertFalse(list(self.output.iterdir()))

    def test_tampered_digest_fails(self):
        self.proposal["proposal_sha256"]="b"*64
        with self.assertRaises(PermissionError):
            self.stage()

    def test_wrong_review_identity_fails(self):
        self.review["proposal_sha256"]="b"*64
        with self.assertRaises(PermissionError):
            self.stage()

    def test_stale_base_fails(self):
        with self.assertRaises(PermissionError):
            self.stage(base_sha="b"*40)

    def test_unapproved_source_change_fails(self):
        self.proposal["changes"][0]["path"]="agent/trusted_docker_executor.py"
        c=json.dumps({k:v for k,v in self.proposal.items() if k!="proposal_sha256"},
                     sort_keys=True,separators=(",",":"),ensure_ascii=True)
        self.proposal["proposal_sha256"]=hashlib.sha256(c.encode("ascii")).hexdigest()
        self.review["proposal_sha256"]=self.proposal["proposal_sha256"]
        with self.assertRaises(PermissionError):
            self.stage()

    def test_budget_exhaustion_fails(self):
        with sqlite3.connect(self.budget) as db:
            db.execute("INSERT INTO gbp_reservations VALUES(?,?,?,?,?,?)",
                       ("old","openai","2026-11-22","5.00","reserved",None))
        with self.assertRaises(PermissionError):
            self.approval()

    def test_cap_cannot_be_increased(self):
        with self.assertRaises(PermissionError):
            inspect_approvals(**{**self.params,"maximum_usd":Decimal("1")})


if __name__=="__main__":
    unittest.main()
