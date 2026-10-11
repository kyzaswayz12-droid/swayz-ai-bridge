import json
import unittest
from agent.response_diagnostics import openai_metadata

class DiagnosticsTests(unittest.TestCase):
    def test_incomplete_reasoning_only_response(self):
        body={"status":"incomplete","incomplete_details":{"reason":"max_output_tokens"},
              "usage":{"input_tokens":15,"output_tokens":32,
                       "output_tokens_details":{"reasoning_tokens":32}},
              "output":[{"type":"reasoning","summary":[]}]}
        result=openai_metadata(json.dumps(body).encode())
        self.assertEqual(result["incomplete_reason"],"max_output_tokens")
        self.assertFalse(result["output_text_present"])
        self.assertEqual(result["reasoning_tokens"],32)

    def test_completed_response(self):
        body={"status":"completed","usage":{"input_tokens":4,"output_tokens":2},
              "output":[{"content":[{"type":"output_text","text":"OK"}]}]}
        result=openai_metadata(json.dumps(body).encode())
        self.assertTrue(result["output_text_present"])
