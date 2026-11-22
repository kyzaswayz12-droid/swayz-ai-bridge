"""Zero-network CI tests for operator-only GPT -> Claude provider handoff."""
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from agent.provider_only_handoff import run_provider_only, _TASK


class ProviderOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.folder = root / "checkpoints"
        self.folder.mkdir(mode=0o700)
        self.stop = root / "stop.db"
        self.budget = root / "budget.db"
        self.creds = root / "providers.env"
        self.creds.write_text(chr(10).join(
            ["OPENAI_API_KEY=test-only-openai", "ANTHROPIC_API_KEY=test-only-claude", ""]))
        self.creds.chmod(0o600)
        self.openai = root / "openai.json"
        self.claude = root / "claude.json"
        self.fx = root / "fx.json"
        common = dict(verified_by_owner=True, verified_on="2026-11-22",
                      expires_on="2026-11-29", source_url="https://example.com/pricing")
        self.openai.write_text(json.dumps(dict(**common, provider="openai",
            model="gpt-5-mini", input_per_million_usd="0.25",
            output_per_million_usd="2.00")))
        self.claude.write_text(json.dumps(dict(**common, provider="anthropic",
            model="claude-haiku-4-5-20251001",input_per_million_usd="1.00",
            output_per_million_usd="5.00")))
        self.fx.write_text(json.dumps(dict(
            base="USD",quote="GBP",gbp_per_usd="0.80",
            verified_by_owner=True,verified_on="2026-11-22",
            expires_on="2026-11-29",source_url="https://example.com/fx")))
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,1)")
        with sqlite3.connect(self.budget) as db:
            db.execute("""CREATE TABLE gbp_reservations(request_id TEXT PRIMARY KEY,
            provider TEXT,day_utc TEXT,reserved_gbp TEXT,status TEXT,actual_gbp TEXT)""")
        self.calls = []
        self.base_sha = "a" * 40
        self.args = dict(job_id="provider-only-test-1",
            base_sha=self.base_sha,checkpoint_dir=self.folder,
            openai_card=self.openai,claude_card=self.claude,fx_card=self.fx,
            credentials_file=self.creds,stop_db=self.stop,gbp_budget_db=self.budget,
            owner_authorised=True,paid_calls_enabled=True,test_mode=True,
            now=datetime(2026,11,22,tzinfo=timezone.utc))

    def fake_transport(self,provider,payload,key):
        self.calls.append(provider)
        if provider == "openai":
            self.assertEqual(key, "test-only-openai")
            self.assertFalse(payload["store"])
            proposal = {
                "base_sha":self.base_sha, "branch":"agent/test-label-only",
                "changes":[{"path":"tests/test_job_label.py",
                            "content":"import unittest\nclass Check(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n"}],
                "proposal_sha256":"0"*64,
            }
            response = {"output":[{"content":[{"type":"output_text",
                           "text":json.dumps(proposal)}]}],
                        "usage":{"input_tokens":150,"output_tokens":120}}
            return json.dumps(response).encode()
        self.assertEqual(key, "test-only-claude")
        self.assertEqual(payload["max_tokens"],512)
        proposal_sha = json.loads(payload["messages"][0]["content"])["proposal_sha256"]
        response = {"stop_reason":"end_turn",
                    "content":[{"type":"text","text":json.dumps({
                        "proposal_sha256":proposal_sha,
                        "approved":True,"findings":[]})}],
                    "usage":{"input_tokens":240,"output_tokens":50}}
        return json.dumps(response).encode()

    def call(self,**overrides):
        args={**self.args, "transport":self.fake_transport}
        args.update(overrides)
        return run_provider_only(**args)

    def ledger(self):
        with sqlite3.connect(self.budget) as db:
            return db.execute("SELECT request_id,reserved_gbp,status FROM gbp_reservations ORDER BY request_id").fetchall()

    def test_two_mocked_responses_recorded_without_execution(self):
        result=self.call()
        self.assertEqual(result["state"],"operator_review_required")
        self.assertEqual(result["paid_calls"],0)
        self.assertFalse(result["execution_authorised"])
        self.assertEqual(self.calls,["openai","anthropic"])
        records=self.ledger()
        self.assertEqual(len(records),2)
        self.assertTrue(all(x[2]=="reserved" for x in records))
        self.assertLess(sum(Decimal(x[1]) for x in records),Decimal("0.05"))
        saved=json.loads((self.folder/"provider-only-test-1.result.json").read_text())
        self.assertFalse(saved["provider_transport_used"])
        self.assertTrue(saved["simulated"])
        self.assertEqual(saved["github_writes"],0)
        self.assertFalse(saved["docker_executed"])
        self.assertTrue((self.folder/"provider-only-test-1.openai-response.json").is_file())
        self.assertTrue((self.folder/"provider-only-test-1.claude-response.json").is_file())
        with sqlite3.connect(self.stop) as db:
            self.assertEqual(db.execute("SELECT stopped FROM agent_control").fetchone(),(1,))

    def test_replay_denied_before_reservation_or_provider_call(self):
        self.call()
        with self.assertRaises(FileExistsError):
            self.call()
        self.assertEqual(self.calls,["openai","anthropic"])
        self.assertEqual(len(self.ledger()),2)

    def test_unapproved_never_calls_transport(self):
        with self.assertRaises(PermissionError):
            self.call(owner_authorised=False)
        self.assertEqual(self.calls,[])
        self.assertEqual(len(self.ledger()),0)

    def test_unstopped_agent_is_rejected(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=0")
        with self.assertRaises(PermissionError):
            self.call()
        self.assertEqual(self.calls,[])
        self.assertEqual(len(self.ledger()),0)

    def test_budget_exhaustion_prevents_network(self):
        with sqlite3.connect(self.budget) as db:
            db.execute("INSERT INTO gbp_reservations VALUES(?,?,?,?,?,?)",
                       ("old","openai","2026-11-22","5.00","reserved",None))
        with self.assertRaises(PermissionError):
            self.call()
        self.assertEqual(self.calls,[])
        self.assertEqual(len(self.ledger()),1)

    def test_gpt_failure_never_calls_claude_or_retries(self):
        def error(provider,payload,key):
            self.calls.append(provider)
            raise RuntimeError("network uncertainty")
        with self.assertRaises(RuntimeError):
            self.call(transport=error)
        self.assertEqual(self.calls,["openai"])
        self.assertEqual(len(self.ledger()),2)
        with self.assertRaises(FileExistsError):
            self.call(transport=error)

    def test_invalid_proposal_never_calls_claude(self):
        def bad(provider,payload,key):
            self.calls.append(provider)
            return json.dumps({
                "output":[{"content":[{"type":"output_text","text":"not-json"}]}],
                "usage":{"input_tokens":5,"output_tokens":5}}).encode()
        with self.assertRaises(ValueError):
            self.call(transport=bad)
        self.assertEqual(self.calls,["openai"])
        self.assertEqual(len(self.ledger()),2)

    def test_production_transport_not_allowed_as_mock(self):
        from agent.http_transport import provider_transport
        with self.assertRaises(PermissionError):
            self.call(transport=provider_transport)

    def test_real_mode_cannot_override_transport(self):
        with self.assertRaises(PermissionError):
            self.call(test_mode=False)
        self.assertEqual(self.calls,[])


if __name__=="__main__":
    unittest.main()
