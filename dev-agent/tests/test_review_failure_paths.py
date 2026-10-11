import json
import tempfile
import unittest
from pathlib import Path
from agent.live_collaboration import run_once
from agent.emergency_stop import EmergencyStop
from test_live_collaboration import cards

class ReviewFailurePathsTests(unittest.TestCase):
    def check(self,kind,expected_reason):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            secrets=p/"providers.env"
            secrets.write_text("OPENAI_API_KEY=fake-openai\nANTHROPIC_API_KEY=fake-claude\n")
            secrets.chmod(0o600)
            stop=p/"stop.db"
            EmergencyStop(str(stop)).close()
            a,b=cards(d)
            calls=[]
            def transport(provider,payload,key):
                calls.append(provider)
                if provider=="openai":
                    return json.dumps({"output":[{"content":[{"type":"output_text","text":"Add risk tests"}]}],"usage":{"input_tokens":10,"output_tokens":20}}).encode()
                if kind=="error":
                    raise TimeoutError("simulated timeout")
                return json.dumps({"stop_reason":"max_tokens","content":[{"type":"text","text":"incomplete"}],"usage":{"input_tokens":20,"output_tokens":512}}).encode()
            with self.assertRaises((TimeoutError,ValueError)):
                run_once("Review tests",secrets=secrets,budget_db=p/"budget.db",
                         control_db=stop,openai_model="gpt-5-mini",
                         claude_model="claude-haiku-4-5-20251001",
                         execute=True,transport=transport,openai_rate_card=a,
                         claude_rate_card=b,checkpoint_dir=p/"checkpoints")
            self.assertEqual(calls,["openai","anthropic"])
            proposals=list((p/"checkpoints").glob("*.json"))
            failure=[f for f in proposals if f.name.endswith(".failure.json")]
            self.assertEqual(len(failure),1)
            self.assertEqual(json.loads(failure[0].read_text())["reason"],expected_reason)
    def test_provider_error(self):
        self.check("error","review_provider_error")
    def test_incomplete(self):
        self.check("incomplete","review_incomplete")
