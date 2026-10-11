import json
import tempfile
import unittest
from pathlib import Path
from agent.live_collaboration import run_once
from agent.emergency_stop import EmergencyStop

def cards(folder):
    p=Path(folder)
    common={"verified_by_owner":True,"verified_on":"2026-10-11",
            "expires_on":"2026-10-18","source_url":"https://example.com/pricing"}
    a={**common,"provider":"openai","model":"gpt-5-mini",
       "input_per_million_usd":"0.25","output_per_million_usd":"2.00"}
    b={**common,"provider":"anthropic","model":"claude-haiku-4-5-20251001",
       "input_per_million_usd":"1.00","output_per_million_usd":"5.00"}
    (p/"openai-rates.json").write_text(json.dumps(a))
    (p/"claude-rates.json").write_text(json.dumps(b))
    return p/"openai-rates.json",p/"claude-rates.json"


class LiveCollaborationTests(unittest.TestCase):
    def test_disabled_mode_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as d:
            result=run_once("Check tests",secrets=Path(d)/"missing",
                budget_db=Path(d)/"budget.db",control_db=Path(d)/"stop.db",
                openai_model="gpt-5-mini",claude_model="claude-haiku-4-5-20251001",execute=False)
            self.assertEqual(result["state"],"disabled")
            self.assertFalse((Path(d)/"budget.db").exists())

    def test_mock_two_provider_cycle(self):
        with tempfile.TemporaryDirectory() as d:
            secrets=Path(d)/"providers.env"
            secrets.write_text("OPENAI_API_KEY=fake-openai\nANTHROPIC_API_KEY=fake-claude\n")
            secrets.chmod(0o600)
            stop=Path(d)/"stop.db"
            EmergencyStop(str(stop)).close()
            a,b=cards(d)
            calls=[]
            def transport(provider,payload,key):
                calls.append(provider)
                if provider=="openai":
                    return json.dumps({"output":[{"content":[{"type":"output_text",
                        "text":"Add tests for risk limits"}]}],
                        "usage":{"input_tokens":15,"output_tokens":20}}).encode()
                task=json.loads(payload["messages"][0]["content"])
                return json.dumps({"content":[{"type":"text","text":json.dumps({
                    "proposal_sha256":task["proposal_sha256"],"approved":True,
                    "findings":["Human review required"]})}],
                    "usage":{"input_tokens":60,"output_tokens":40}}).encode()
            result=run_once("Improve validation",secrets=secrets,
                budget_db=Path(d)/"budget.db",control_db=stop,
                openai_model="gpt-5-mini",claude_model="claude-haiku-4-5-20251001",execute=True,
                transport=transport,openai_rate_card=a,claude_rate_card=b)
            self.assertEqual(calls,["openai","anthropic"])
            self.assertEqual(len(list((Path(d)/"checkpoints").glob("*.json"))),1)
            self.assertEqual(result["state"],"approval_required")
            self.assertGreater(float(result["reserved_usd"]),0)
            self.assertLess(float(result["reserved_usd"]),0.10)

    def test_missing_stop_prevents_calls(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PermissionError):
                run_once("Test",secrets=Path(d)/"missing",
                    budget_db=Path(d)/"budget.db",control_db=Path(d)/"missing.db",
                    openai_model="gpt-5-mini",claude_model="claude-haiku-4-5-20251001",execute=True,
                    transport=lambda *args:self.fail("Unexpected provider call"))

    def test_no_openai_text_prevents_claude_call(self):
        with tempfile.TemporaryDirectory() as d:
            secrets=Path(d)/"providers.env"
            secrets.write_text("OPENAI_API_KEY=fake-openai\nANTHROPIC_API_KEY=fake-claude\n")
            secrets.chmod(0o600)
            stop=Path(d)/"stop.db"
            EmergencyStop(str(stop)).close()
            a,b=cards(d)
            calls=[]
            def transport(provider,payload,key):
                calls.append(provider)
                return json.dumps({"status":"incomplete",
                    "incomplete_details":{"reason":"max_output_tokens"},
                    "output":[{"type":"reasoning","summary":[]}],
                    "usage":{"input_tokens":15,"output_tokens":1024}}).encode()
            with self.assertRaisesRegex(ValueError,"no usable proposal"):
                run_once("Check tests",secrets=secrets,
                    budget_db=Path(d)/"budget.db",control_db=stop,
                    openai_model="gpt-5-mini",claude_model="claude-haiku-4-5-20251001",execute=True,
                    transport=transport,openai_rate_card=a,claude_rate_card=b)
            self.assertEqual(calls,["openai"])
            import sqlite3
            with sqlite3.connect(Path(d)/"budget.db") as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0],1)
