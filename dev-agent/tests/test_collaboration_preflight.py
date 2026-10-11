import json
import tempfile
import unittest
from pathlib import Path
from datetime import date
from agent.collaboration_preflight import preflight

class CollaborationPreflightTests(unittest.TestCase):
    def test_missing_cards_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                preflight("Review tests",openai_card=Path(d)/"a",
                          claude_card=Path(d)/"b")
    def test_valid_matching_cards(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            common={"verified_by_owner":True,"verified_on":"2026-10-11",
                    "expires_on":"2026-10-18","source_url":"https://example.com/pricing"}
            a={**common,"provider":"openai","model":"gpt-5-mini",
               "input_per_million_usd":"0.25","output_per_million_usd":"2.00"}
            b={**common,"provider":"anthropic","model":"claude-haiku-4-5-20251001",
               "input_per_million_usd":"1.00","output_per_million_usd":"5.00"}
            (p/"a").write_text(json.dumps(a))
            (p/"b").write_text(json.dumps(b))
            result=preflight("Review tests",openai_card=p/"a",claude_card=p/"b",
                             openai_model=a["model"],claude_model=b["model"])
            self.assertEqual(result["provider_calls"],0)
            self.assertEqual(result["state"],"preflight_passed")
