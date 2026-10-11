import json
import tempfile
import unittest
from pathlib import Path
from agent.live_collaboration import run_once
from agent.emergency_stop import EmergencyStop
from test_live_collaboration import cards

class FailedReviewCheckpointTests(unittest.TestCase):
    def test_invalid_review_preserves_proposal_without_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            secrets=root/"providers.env"
            secrets.write_text("OPENAI_API_KEY=fake-openai\nANTHROPIC_API_KEY=fake-claude\n")
            secrets.chmod(0o600)
            stop=root/"stop.db"
            EmergencyStop(str(stop)).close()
            a,b=cards(d)
            calls=[]
            def transport(provider,payload,key):
                calls.append(provider)
                if provider=="openai":
                    return json.dumps({"output":[{"content":[{"type":"output_text","text":"Propose tests for risk limits"}]}],"usage":{"input_tokens":20,"output_tokens":30}}).encode()
                return json.dumps({"content":[{"type":"text","text":"not json"}],"usage":{"input_tokens":40,"output_tokens":10},"stop_reason":"end_turn"}).encode()
            with self.assertRaisesRegex(ValueError,"Claude review invalid"):
                run_once("Review risk tests",secrets=secrets,budget_db=root/"budget.db",
                         control_db=stop,openai_model="gpt-5-mini",
                         claude_model="claude-haiku-4-5-20251001",execute=True,
                         transport=transport,openai_rate_card=a,claude_rate_card=b,
                         checkpoint_dir=root/"checkpoints")
            self.assertEqual(calls,["openai","anthropic"])
            files=[p for p in (root/"checkpoints").glob("*.json") if not p.name.endswith(".failure.json")]
            self.assertEqual(len(files),1)
            record=json.loads(files[0].read_text())
            failure=root/"checkpoints"/(record["proposal_sha256"]+".failure.json")
            self.assertEqual(json.loads(failure.read_text())["reason"],"review_invalid_json")
            self.assertEqual(record["proposal"],"Propose tests for risk limits")
            self.assertEqual(record["review_state"],"pending")
