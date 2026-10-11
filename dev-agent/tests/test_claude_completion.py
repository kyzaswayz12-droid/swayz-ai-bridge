import json
import unittest
from agent.providers import anthropic_response

class ClaudeCompletionTests(unittest.TestCase):
    def response(self, reason):
        return json.dumps({"stop_reason":reason,"content":[{"type":"text","text":"{\"approved\":false}"}],"usage":{"input_tokens":10,"output_tokens":20}}).encode()
    def test_max_tokens_rejected(self):
        with self.assertRaisesRegex(ValueError,"Incomplete Claude"):
            anthropic_response(self.response("max_tokens"))
    def test_pause_turn_rejected(self):
        with self.assertRaisesRegex(ValueError,"Incomplete Claude"):
            anthropic_response(self.response("pause_turn"))
    def test_end_turn_accepted(self):
        self.assertEqual(anthropic_response(self.response("end_turn")).output_tokens,20)
