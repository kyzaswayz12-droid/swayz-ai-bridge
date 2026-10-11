import json
import unittest
from agent.providers import (openai_response,anthropic_response,
    prepare_openai_request,prepare_anthropic_request)

class ProviderTests(unittest.TestCase):
    def test_openai_parsing(self):
        body={"output":[{"content":[{"type":"output_text","text":"Reviewed"}]}],
              "usage":{"input_tokens":12,"output_tokens":5}}
        result=openai_response(json.dumps(body).encode())
        self.assertEqual((result.text,result.input_tokens,result.output_tokens),("Reviewed",12,5))

    def test_anthropic_parsing(self):
        body={"content":[{"type":"text","text":"Approved"}],
              "usage":{"input_tokens":10,"output_tokens":3}}
        result=anthropic_response(json.dumps(body).encode())
        self.assertEqual(result.text,"Approved")

    def test_malformed_usage_rejected(self):
        with self.assertRaises(ValueError):
            openai_response(b'{"output":[{"content":[{"type":"output_text","text":"hi"}]}],"usage":{"input_tokens":-1,"output_tokens":2}}')
        with self.assertRaises(ValueError):
            anthropic_response(b'{"content":[{"type":"text","text":"hi"}],"usage":{}}')

    def test_request_limits(self):
        self.assertFalse(prepare_openai_request("model","review","task")["store"])
        self.assertEqual(prepare_anthropic_request("model","review","task")["max_tokens"],1500)
        with self.assertRaises(ValueError):
            prepare_openai_request("model","review","task",max_output_tokens=999999)
